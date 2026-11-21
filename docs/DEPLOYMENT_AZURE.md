# Azure Container Apps (ACA) & AKS Deployment Guide
## Nemawashi Enterprise Multi-Agent Governance Engine

This guide provides production-ready instructions for deploying the **Nemawashi Enterprise Multi-Agent Governance Engine** non-root container image (`UID 10001`, `GID 10001`) to **Azure Container Apps (ACA)**—with an equivalent **Azure Kubernetes Service (AKS)** persistent volume configuration—using **Azure Container Registry (ACR)**, **Azure Files**, and **Azure Key Vault**.

Following this blueprint ensures:
- **Non-Root Security Posture**: Runs the hardened `python:3.12-slim` image as `nemawashi` (`UID 10001`, `GID 10001`) with `ENVIRONMENT=production` fail-closed secret validation.
- **Persistent Audit & HITL Lineage**: Azure Files SMB/NFS mounts preserve `nemawashi_ledger.jsonl`, `FileLock` mutexes, semantic cache entries, and HMAC-signed suspended states across container restarts.
- **Zero-Trust Secret Management**: `NEMAWASHI_WEBHOOK_SECRET` and `GEMINI_API_KEY` are injected from **Azure Key Vault** via Managed Identity.
- **Automated Health & Readiness**: Native HTTP probes on port `8000` (`/health` liveness and `/ready` readiness).

---

## Architecture Overview

```text
                                 Azure Cloud (ACA / AKS)
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  Azure Container Registry (ACR): <acr_name>.azurecr.io/nemawashi-gateway:v1.1.0        │
│                                                                                        │
│  Azure Container Apps Environment (or AKS Cluster)                                     │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │ Container: nemawashi-gateway (UID 10001, 1.0 vCPU, 2.0 GiB RAM / 2048Mi)         │  │
│  │                                                                                  │  │
│  │   • Ingress: Port 8000 (HTTPS terminated at ACA Envoy / Ingress Controller)      │  │
│  │   • Probes:  Liveness GET /health:8000  |  Readiness GET /ready:8000             │  │
│  │   • Secrets: Azure Key Vault -> NEMAWASHI_WEBHOOK_SECRET, GEMINI_API_KEY         │  │
│  └───────────┬──────────────────────────┬──────────────────────────┬────────────────┘  │
│              │                          │                          │                   │
│              ▼                          ▼                          ▼                   │
│  Azure Files Share (SMB 3.1.1 / NFSv4.1, POSIX UID/GID 10001):                         │
│    ├── /app/audit_logs               (nemawashi_ledger.jsonl + .lock)                  │
│    ├── /app/cache                    (semantic_cache.json + .lock)                     │
│    └── /app/storage/suspended_states (HMAC-signed HITL checkpoints + .lock)            │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Provision Resource Group & Push Image to ACR

```bash
# 1. Define deployment variables
RESOURCE_GROUP="rg-nemawashi-prod"
LOCATION="eastus"
ACR_NAME="acrnemawashiprod"
IMAGE_TAG="v1.1.0"

# 2. Create Resource Group and Azure Container Registry
az group create --name "$RESOURCE_GROUP" --location "$LOCATION"
az acr create --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" --sku Basic --admin-enabled false

# 3. Build and push the non-root container image directly to ACR
az acr build \
  --registry "$ACR_NAME" \
  --image "nemawashi-gateway:${IMAGE_TAG}" \
  --file Dockerfile .
```

---

## Step 2: Configure Azure Files Persistent Storage (`UID 10001`)

Nemawashi requires persistent, `FileLock`-compatible storage for `/app/audit_logs`, `/app/cache`, and `/app/storage/suspended_states` so the chained SHA-256 ledger and suspended HITL states survive container revisions.

> [!IMPORTANT]
> When mounting **Azure Files** over SMB or NFS into the non-root container (`UID 10001`, `GID 10001`), set `file_mode=0770,dir_mode=0770,uid=10001,gid=10001` (SMB) or `chown -R 10001:10001` (NFSv4.1) so the `nemawashi` user has read/write/lock permissions.

```bash
STORAGE_ACCOUNT="stnemawashiprod"
ACA_ENV="aca-env-nemawashi"

# 1. Create Storage Account and three Azure File Shares
az storage account create \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2

STORAGE_KEY=$(az storage account keys list \
  --resource-group "$RESOURCE_GROUP" \
  --account-name "$STORAGE_ACCOUNT" \
  --query "[0].value" -o tsv)

for SHARE in nemawashi-audit-logs nemawashi-cache nemawashi-suspended-states; do
  az storage share-rm create \
    --resource-group "$RESOURCE_GROUP" \
    --storage-account "$STORAGE_ACCOUNT" \
    --name "$SHARE" \
    --quota 10
done

# 2. Create Container Apps Environment and bind Azure Files storage
az containerapp env create \
  --name "$ACA_ENV" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION"

for SHARE in nemawashi-audit-logs nemawashi-cache nemawashi-suspended-states; do
  az containerapp env storage set \
    --name "$ACA_ENV" \
    --resource-group "$RESOURCE_GROUP" \
    --storage-name "$SHARE" \
    --azure-file-account-name "$STORAGE_ACCOUNT" \
    --azure-file-account-key "$STORAGE_KEY" \
    --azure-file-share-name "$SHARE" \
    --access-mode ReadWrite
done
```

---

## Step 3: Store Secrets in Azure Key Vault

In production (`ENVIRONMENT=production`), `src/nemawashi/main.py` fails closed (`RuntimeError`) if `NEMAWASHI_WEBHOOK_SECRET` is unset or matches a default placeholder.

```bash
KV_NAME="kv-nemawashi-prod"
WEBHOOK_SECRET=$(openssl rand -hex 32)

# 1. Create Key Vault with RBAC authorization
az keyvault create \
  --name "$KV_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --enable-rbac-authorization true

# 2. Store NEMAWASHI_WEBHOOK_SECRET and GEMINI_API_KEY
az keyvault secret set --vault-name "$KV_NAME" --name "nemawashi-webhook-secret" --value "$WEBHOOK_SECRET"
az keyvault secret set --vault-name "$KV_NAME" --name "gemini-api-key" --value "<YOUR_GEMINI_API_KEY>"
```

---

## Step 4: Deploy to Azure Container Apps (ACA)

Deploy the container with `2.0Gi` memory (`2048Mi`), `min-replicas 1` (single-writer `FileLock` consistency for local JSONL ledger), Managed Identity access to Key Vault and ACR, and HTTP probes on port `8000`.

```bash
APP_NAME="nemawashi-gateway"

# 1. Create the Container App with system-assigned Managed Identity
az containerapp create \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ACA_ENV" \
  --image "${ACR_NAME}.azurecr.io/nemawashi-gateway:${IMAGE_TAG}" \
  --registry-server "${ACR_NAME}.azurecr.io" \
  --registry-identity system \
  --system-assigned \
  --ingress external \
  --target-port 8000 \
  --cpu 1.0 \
  --memory 2.0Gi \
  --min-replicas 1 \
  --max-replicas 1 \
  --env-vars \
    "ENVIRONMENT=production" \
    "GEMINI_MODEL_NAME=gemini-2.5-flash" \
    "NEMAWASHI_MAX_ROUNDS=3" \
    "NEMAWASHI_AUDIT_LOG_DIR=/app/audit_logs" \
    "NEMAWASHI_CACHE_DIR=/app/cache" \
    "NEMAWASHI_STATE_DIR=/app/storage/suspended_states"

# 2. Grant the Managed Identity "Key Vault Secrets User" on the Key Vault
PRINCIPAL_ID=$(az containerapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --query "identity.principalId" -o tsv)
KV_ID=$(az keyvault show --name "$KV_NAME" --resource-group "$RESOURCE_GROUP" --query "id" -o tsv)
az role assignment create --assignee "$PRINCIPAL_ID" --role "Key Vault Secrets User" --scope "$KV_ID"

# 3. Bind Key Vault secrets to environment variables
az containerapp secret set \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --secrets \
    "webhook-secret=keyvaultref:https://${KV_NAME}.vault.azure.net/secrets/nemawashi-webhook-secret,identityref:system" \
    "gemini-key=keyvaultref:https://${KV_NAME}.vault.azure.net/secrets/gemini-api-key,identityref:system"

az containerapp update \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --set-env-vars \
    "NEMAWASHI_WEBHOOK_SECRET=secretref:webhook-secret" \
    "GEMINI_API_KEY=secretref:gemini-key"
```

### 4.1 Volume Mounts & HTTP Probes (`aca-containerapp.yaml`)

Export and apply the volume mounts (`UID 10001` ownership via Azure Files `mountOptions`) and `/health` + `/ready` HTTP probes on port `8000`:

```yaml
properties:
  template:
    containers:
      - name: nemawashi-gateway
        image: acrnemawashiprod.azurecr.io/nemawashi-gateway:v1.1.0
        resources:
          cpu: 1.0
          memory: 2.0Gi
        probes:
          - type: Liveness
            httpGet:
              path: /health
              port: 8000
              scheme: HTTP
            initialDelaySeconds: 5
            periodSeconds: 30
            timeoutSeconds: 5
            failureThreshold: 3
          - type: Readiness
            httpGet:
              path: /ready
              port: 8000
              scheme: HTTP
            initialDelaySeconds: 5
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
        volumeMounts:
          - volumeName: audit-logs-vol
            mountPath: /app/audit_logs
          - volumeName: cache-vol
            mountPath: /app/cache
          - volumeName: state-vol
            mountPath: /app/storage/suspended_states
    volumes:
      - name: audit-logs-vol
        storageType: AzureFile
        storageName: nemawashi-audit-logs
        mountOptions: "uid=10001,gid=10001,dir_mode=0770,file_mode=0770"
      - name: cache-vol
        storageType: AzureFile
        storageName: nemawashi-cache
        mountOptions: "uid=10001,gid=10001,dir_mode=0770,file_mode=0770"
      - name: state-vol
        storageType: AzureFile
        storageName: nemawashi-suspended-states
        mountOptions: "uid=10001,gid=10001,dir_mode=0770,file_mode=0770"
```

Apply the declarative manifest:
```bash
az containerapp update \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --yaml aca-containerapp.yaml
```

---

## Alternative: Azure Kubernetes Service (AKS)

If deploying to **AKS** instead of ACA, use the `azurefile-csi` StorageClass with `mountOptions` for `UID 10001` (`uid=10001,gid=10001,dir_mode=0770,file_mode=0770`), mount the three PVCs to `/app/audit_logs`, `/app/cache`, and `/app/storage/suspended_states`, and configure identical `livenessProbe` (`GET /health:8000`) and `readinessProbe` (`GET /ready:8000`) in your `Deployment` spec with `securityContext.runAsUser: 10001` and `runAsGroup: 10001`.
