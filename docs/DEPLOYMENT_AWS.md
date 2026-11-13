# AWS EC2 Free Tier Deployment Guide
## Nemawashi Enterprise Multi-Agent Governance Engine

This guide provides end-to-end, production-accurate instructions for deploying the **Nemawashi Enterprise Multi-Agent Governance Engine** on an **AWS EC2 Free Tier** virtual machine (`t2.micro` or `t3.micro`) using **Docker** and **Docker Compose**.

Following this blueprint ensures:
- **100% Free Tier Compliance**: Operates well within the 750 hours/month Amazon EC2 compute allowance and 30 GB EBS storage budget.
- **Low Memory Footprint**: Python 3.12 + FastAPI idle footprint is $< 220\text{MB}$ RAM, safely inside the 1.0 GiB physical limit.
- **Persistent Audit & State Lineage**: Chained SHA-256 audit ledgers, vector cache entries, and suspended states are persisted directly on host EBS volume mounts.
- **Enterprise Security Posture**: Non-root container execution (UID `10001`), hardened security groups, and mandatory HMAC-SHA256 authenticated callback ingress.

---

## Architecture Overview

```
                                      AWS EC2 Cloud (Free Tier)
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│  Instance: t2.micro / t3.micro (1 vCPU, 1 GiB RAM, 8-30 GB gp3 EBS)                        │
│  OS: Ubuntu 24.04 LTS Minimal or Amazon Linux 2023                                          │
│                                                                                             │
│  Security Group Inbound Rules:                                                              │
│    • TCP 22   (SSH)              ──> Restricted to "My IP"                                  │
│    • TCP 8000 (FastAPI Gateway)  ──> Internal API Swarm CIDR or Trusted Reverse Proxy       │
│                                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ Container: nemawashi-governance-engine (Docker Compose, unprivileged user UID 10001)  │  │
│  │                                                                                       │  │
│  │   • Ingress Endpoints: GET /health, GET /docs, POST /resume                           │  │
│  │   • LangGraph Deliberation Machine & FileLock SHA-256 Chained Ledger                  │  │
│  │   • Memory Consumption: ~180MB idle, ~350MB peak deliberation                         │  │
│  └──────────────────────────────────────────────────┬────────────────────────────────────┘  │
│                                                     │ Volume Bind Mounts                    │
│                                                     ▼                                       │
│  Host EBS Filesystem (/home/ubuntu/nemawashi):                                              │
│    ├── audit_logs/nemawashi_ledger.jsonl (Chained SHA-256 immutable ledger)                 │
│    ├── cache/semantic_cache.json         (Local vector similarity index)                    │
│    └── storage/suspended_states/        (Non-blocking HMAC-signed serialized states)       │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Launch an AWS EC2 Free Tier Instance

### 1.1 Choose Amazon Machine Image (AMI)
1. Sign in to the [AWS Management Console](https://console.aws.amazon.com/ec2/).
2. Navigate to **EC2** $\rightarrow$ **Launch Instance**.
3. **Name**: `nemawashi-governance-node-01`
4. **Application and OS Images (AMI)**: Select **Ubuntu Server 24.04 LTS (HVM), SSD Volume Type** (marked *"Free tier eligible"*) or **Amazon Linux 2023 AMI**.
5. **Architecture**: `64-bit (x86)`.

### 1.2 Select Instance Type
- Choose **`t2.micro`** (1 vCPU, 1.0 GiB Memory).
  *(Note: In regions where `t2.micro` is not available, select **`t3.micro`**, which is also Free Tier eligible).*

### 1.3 Key Pair (Login)
- Select an existing key pair or click **Create new key pair** (`nemawashi-ec2-key.pem`).
- Save the `.pem` file to your local `~/.ssh/` directory and set read-only permissions:
  ```bash
  chmod 400 ~/.ssh/nemawashi-ec2-key.pem
  ```

### 1.4 Configure Network & Security Group
In the **Network settings** panel, click **Edit**:
- **Auto-assign public IP**: `Enable`
- **Security group rules**:
  | Type | Protocol | Port Range | Source | Description |
  |---|---|---|---|---|
  | **SSH** | TCP | `22` | `My IP` | Secure administrative shell access |
  | **Custom TCP** | TCP | `8000` | `Custom` (Your IP or Agent Swarm CIDR) | FastAPI Governance Gateway & Swagger UI |

> [!CAUTION]
> Never open port `22` or `8000` to `0.0.0.0/0` (Anywhere) without an authenticating reverse proxy or strict API key firewall.

### 1.5 Configure Storage
- **Volume Type**: General Purpose SSD (`gp3`).
- **Size**: `15 GiB` (Free tier includes up to 30 GiB of EBS storage).
- Click **Launch Instance**.

---

## Step 2: Connect and Install Docker Engine & Compose

### 2.1 SSH into your EC2 Instance
```bash
ssh -i ~/.ssh/nemawashi-ec2-key.pem ubuntu@<YOUR_EC2_PUBLIC_IPV4_DNS>
```

### 2.2 Update System Packages & Install Docker
Run the following commands on the remote Ubuntu VM:

```bash
# Update package repositories
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker Engine and the official Docker Compose v2 plugin
sudo apt-get install -y docker.io docker-compose-v2 git curl openssl

# Enable and start Docker service
sudo systemctl enable --now docker

# Add ubuntu user to docker group (avoids typing sudo for docker commands)
sudo usermod -aG docker ubuntu

# Apply group changes to current session
newgrp docker

# Verify Docker installation
docker --version
docker compose version
```

---

## Step 3: Clone Repository, Configure Secrets & Permissions

### 3.1 Clone the Codebase
```bash
cd ~
git clone https://github.com/JayZamindar/nemawashi-enterprise-governance-engine.git nemawashi
cd nemawashi
```

### 3.2 Configure `.env` Environment File
Generate a cryptographically secure 32-byte secret for `NEMAWASHI_WEBHOOK_SECRET` using `openssl`:

```bash
# Generate high-entropy 64-character hex secret
WEBHOOK_SECRET=$(openssl rand -hex 32)
echo "Generated Secret: $WEBHOOK_SECRET"

# Create .env file from template
cat <<EOF > .env
# Nemawashi Runtime Environment Configuration
NEMAWASHI_WEBHOOK_SECRET=${WEBHOOK_SECRET}
NEMAWASHI_MAX_ROUNDS=3

# Optional: Add your Google Gemini API Key for live LLM consensus turns
# (Leave blank to run in deterministic zero-cost offline rule-based mode)
GEMINI_API_KEY=

# Persistent container path overrides (aligned with host volume mounts)
NEMAWASHI_AUDIT_LOG_DIR=/app/audit_logs
NEMAWASHI_CACHE_DIR=/app/cache
NEMAWASHI_STATE_DIR=/app/storage
EOF

# Lock down .env file permissions
chmod 600 .env
```

### 3.3 Create Persistent Directories with Proper Ownership
The production Docker container runs under an unprivileged user (`nemawashi`, UID `10001`, GID `10001`). Create the host bind mount directories and set ownership accordingly:

```bash
# Create local directories for ledger, cache, and suspended states
mkdir -p audit_logs cache storage/suspended_states

# Grant ownership to non-root container UID 10001
sudo chown -R 10001:10001 audit_logs cache storage
sudo chmod -R 775 audit_logs cache storage
```

---

## Step 4: Build and Start the Governance Engine

### 4.1 Launch with Docker Compose
```bash
docker compose up -d --build
```

### 4.2 Inspect Container Health & Status
```bash
# Check container status (should show "Up" and "healthy")
docker compose ps

# Follow container runtime logs
docker compose logs -f
```

You should observe output similar to:
```text
nemawashi-governance-engine | INFO:     Started server process [1]
nemawashi-governance-engine | INFO:     Waiting for application startup.
nemawashi-governance-engine | INFO:     Application startup complete.
nemawashi-governance-engine | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

---

## Step 5: Verify Live Endpoints & HMAC Callback Security

### 5.1 Test Health & Documentation Endpoints
From your local machine (or via curl on the instance):

```bash
# 1. Healthcheck probe
curl -i http://localhost:8000/health
# Expected: HTTP 200 OK {"status":"healthy",...}

# 2. Interactive Swagger OpenAPI documentation
curl -i http://localhost:8000/docs
# Expected: HTTP 200 OK (HTML response)
```

### 5.2 Test HMAC-SHA256 Resumption Security
Verify that the `POST /resume` endpoint rejects unsigned requests and accepts valid cryptographic HMAC signatures:

```bash
# 1. Test missing signature (must return HTTP 401 Unauthorized)
curl -i -X POST http://localhost:8000/resume \
  -H "Content-Type: application/json" \
  -d '{"proposal_id": "p-demo-01", "approved": true, "rationale": "Direct unauthorized attempt"}'

# 2. Compute valid signature using your NEMAWASHI_WEBHOOK_SECRET
SECRET=$(grep NEMAWASHI_WEBHOOK_SECRET .env | cut -d '=' -f2)
PROPOSAL_ID="p-demo-01"
APPROVED="true"
RATIONALE="Authorized by VP of Infrastructure after review"
MESSAGE="${PROPOSAL_ID}:${APPROVED}:${RATIONALE}"

SIGNATURE=$(echo -n "$MESSAGE" | openssl dgst -sha256 -hmac "$SECRET" | cut -d ' ' -f2)
echo "Generated Signature: sha256=$SIGNATURE"

# 3. Test valid signature transmission
curl -i -X POST http://localhost:8000/resume \
  -H "Content-Type: application/json" \
  -H "X-Nemawashi-Signature: sha256=${SIGNATURE}" \
  -d "{\"proposal_id\": \"${PROPOSAL_ID}\", \"approved\": true, \"rationale\": \"${RATIONALE}\"}"
```

---

## Step 6: AWS Cost Hygiene & Free Tier Management

To ensure zero unwanted AWS billing while running 24/7 on the Free Tier:

### 6.1 Set Up an AWS Billing Alarm ($1.00 USD)
1. Open the **AWS Billing and Cost Management Console** $\rightarrow$ **Budgets**.
2. Click **Create budget** $\rightarrow$ **Cost budget**.
3. Set budget amount: `$1.00 USD`.
4. Configure an email notification alert when actual or forecasted spend exceeds 80% ($0.80 USD).

### 6.2 Free Tier Guardrails Checklist
- [x] **Instance Count**: Exactly **1** `t2.micro` (or `t3.micro`) instance running in the account (1 instance $\times$ 744 hours in a 31-day month $\le$ 750 free hours).
- [x] **EBS Volume Allocation**: Total EBS volume size across the account is $\le 30\text{ GiB}$ (our instance uses 15 GiB).
- [x] **Elastic IP Addresses**: Do NOT allocate an unattached Elastic IP (AWS charges for unused Elastic IPs). Use the auto-assigned public IP or DNS.
- [x] **Data Transfer Out**: Free tier includes 100 GB of internet data transfer out per month. JSON payload traffic will consume $< 100\text{MB}$ monthly.

---

## Troubleshooting & Maintenance

### How to View Audit Ledger Records on Host
```bash
cat ~/nemawashi/audit_logs/nemawashi_ledger.jsonl | jq .
```

### How to Verify Ledger Chain Cryptographic Integrity
```bash
docker compose exec nemawashi-gateway python -c "
from nemawashi.audit.ledger import verify_ledger_chain
valid, msg = verify_ledger_chain()
print('Audit Chain Integrity:', valid, '-', msg)
"
```

### How to Restart or Update the Service
```bash
cd ~/nemawashi
git pull origin main
docker compose down
docker compose up -d --build
```
