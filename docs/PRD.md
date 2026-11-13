# Product Requirements Document (PRD)
## Nemawashi Enterprise Multi-Agent Governance Engine

---

## 1. Document Control & Executive Summary

### 1.1 Document Metadata

| Attribute | Specification |
|---|---|
| **Document ID** | `NMW-PRD-2026-V1` |
| **Document Title** | Nemawashi Enterprise Multi-Agent Governance Engine Product Requirements Document |
| **Version** | `1.0.0` |
| **Status** | `APPROVED` |
| **Classification** | Enterprise Confidential / Architectural Standard |
| **Author** | Principal AI Systems Engineer |
| **Target Runtime** | CPython 3.12 (managed via `uv` in `.venv`) |
| **Target Deployment** | Containerized `python:3.12-slim` on AWS EC2 Free Tier (`t2.micro` / `t3.micro`) |
| **Document Hierarchy** | [`GEMINI.md`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/GEMINI.md) $\rightarrow$ `TRD.md` $\rightarrow$ [`PRD.md`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/PRD.md) $\rightarrow$ [`URD.md`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/URD.md) $\rightarrow$ [`IMPLEMENTATION_PLAN.md`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/IMPLEMENTATION_PLAN.md) |

### 1.2 Executive Summary & Problem Statement

Modern enterprise technology organizations are rapidly deploying autonomous AI agent swarms to automate cloud infrastructure scaling, database migrations, security remediation, and CI/CD operations. However, this shift introduces severe systemic risks:
1. **Unilateral Action Vulnerability**: Autonomous agents operating in isolation frequently execute destructive, high-blast-radius, or non-compliant modifications (e.g., dropping database tables, provisioning unbudgeted GPU clusters, opening public security groups `0.0.0.0/0`) without cross-functional oversight.
2. **Infinite Mitigation Loop Token Drain**: Conflicting feedback between agents can create unbounded negotiation loops, rapidly draining LLM API quotas with zero financial or temporal circuit breakers.
3. **Consensus Amnesia**: In naive state architectures, downstream agent outputs overwrite upstream decisions, obliterating preceding security or compliance objections.
4. **Context Dilution & Persona Drift**: Free-form conversational chatter between agents inflates token consumption, introduces hallucinations, and degrades deterministic reasoning.
5. **Audit Trail Mutability**: Unchained or post-hoc log generation fails enterprise non-repudiation and external regulatory standards.

### 1.3 The Nemawashi Solution

The **Nemawashi Enterprise Multi-Agent Governance Engine** solves these challenges by implementing the Japanese corporate principle of *Nemawashi* (根回し) — laying the groundwork and establishing quiet, structured consensus before any formal action is executed. 

The product enforces:
- **Pre-Execution Gatekeeping**: Every operational proposal submitted by an autonomous worker agent must clear deterministic policy rules and a sequential multi-stakeholder consensus circle before any API call touches production infrastructure.
- **Zero Conversational Chatter**: Agents deliberate exclusively through immutable, strongly-typed structured contracts (`StructuredAgentVote`), completely banning free-form conversational chatter.
- **Deterministic Guardrails & Bounded Execution**: A hard watchdog circuit breaker halts negotiation loops at a pre-set ceiling, while an integrated semantic cache bypasses deliberation for semantically identical proposals to reduce latency and token burn.
- **Asynchronous, Cryptographically-Secured Human Oversight**: When risk thresholds are breached, the engine checkpoints execution state, emits non-blocking webhook notifications, and resumes only upon receiving an HMAC-SHA256 signed approval token via a secure API gateway.
- **Tamper-Evident SHA-256 Ledger Lineage**: All deliberation rounds, stakeholder votes, token economics, and final resolutions are sealed into an immutable, forward-secure chained audit log protected by cross-platform file mutex locking.

---

## 2. Product Goals & Measurable Success Metrics (KPIs)

The engine must satisfy rigorous performance, financial, and architectural Service Level Agreements (SLAs). The table below establishes the non-negotiable success metrics for Version 1.0.0:

| Objective Area | Target Key Performance Indicator (KPI) | Target SLA / Metric Budget | Business & Architectural Impact |
|---|---|---|---|
| **Deterministic Pre-Check** | Hard policy evaluation latency | $< 5\text{ms}$ | Instantly vetoes blacklisted actions without consuming LLM inference tokens. |
| **Semantic Cache Guardrail** | Vector cache hit lookup latency | $< 10\text{ms}$ | Serves identical past decisions near-instantaneously, saving 100% of LLM turn costs. |
| **Semantic Matching Precision** | Cosine similarity threshold for cache hit | $\ge 0.95$ | Prevents false-positive bypasses on subtly different infrastructure payloads. |
| **Offline Deliberation Cycle** | Full 4-agent circle evaluation (offline rule-based mode) | $< 1.5\text{s}$ | Enables rapid, zero-cost GitHub Actions CI/CD pipeline verification. |
| **Live Gemini Inference Turn** | Per-agent structured turn latency via Gemini 2.5 Flash | $< 3.0\text{s}$ | Maintains responsive execution for real-time operational agent workflows. |
| **Consensus Amnesia Rate** | Upstream vote loss or overwrite occurrences | `0%` | Strictly enforced by monomorphic reducer state channels. |
| **Reducer Inflation Immunity** | Multi-vote injection rejection via collection inputs | `100%` | Reducers immediately raise type errors on collection inputs. |
| **Loop Watchdog Reliability** | Infinite mitigation loop occurrences exceeding `max_rounds` | `0 incidents` | Watchdog break evaluates as the first priority check in the router. |
| **Cryptographic Audit Integrity** | SHA-256 ledger tamper and byte-corruption detection | `100%` | Forward-linked hashes immediately invalidate on single-byte mutations. |
| **Audit Mutex Concurrency** | Race condition corrupted ledger entries under concurrent writes | `0 incidents` | Cross-platform mutex locking serializes ledger append operations. |
| **HITL Resumption Security** | Unauthorized or forged `/resume` callback acceptance | `0 occurrences` | Mandatory HMAC-SHA256 signature verification using constant-time comparison. |
| **Resource Efficiency** | Idle container memory footprint on AWS EC2 Free Tier | $< 250\text{MB}$ | Ensures stable operation on `t2.micro` / `t3.micro` (1 GB total RAM). |

---

## 3. Target Audience & User Personas Summary

The governance engine serves five primary stakeholder personas across the enterprise. For comprehensive actor profiles, operational permissions, and RACI matrices, refer to [`URD.md`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/URD.md) (Section 2).

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Enterprise Stakeholder Personas                       │
├──────────────────────────┬───────────────────────────┬──────────────────────────┤
│ PER-01: Executive        │ PER-02: Autonomous        │ PER-03 to PER-06: Domain │
│ Gatekeeper / Operator    │ Worker Agent              │ Stakeholder Agents       │
│ • VP Infrastructure / SRE│ • Swarm worker submitting │ • Security Guardian      │
│ • Reviews escalated high-│   operational proposals   │ • Compliance Arbiter     │
│   cost/blast operations  │ • Consumes binary verdicts│ • FinOps Arbiter         │
│ • Signs HMAC callbacks   │   (Permitted / Vetoed)    │ • SRE Sentinel           │
├──────────────────────────┴───────────────────────────┴──────────────────────────┤
│ PER-07 & PER-08: Governance Intelligence Personas                               │
│ • Consensus Arbiter: Synthesizes multi-agent verdicts, deduplicates mitigations │
│ • Adaptive Cost Optimizer: Rightsizes over-budget cloud resource payloads        │
├─────────────────────────────────────────────────────────────────────────────────┤
│ PER-09: Internal & External Regulatory Auditor                                   │
│ • Inspects SHA-256 hash chains, verifies non-repudiation and GDPR/SOC 2 proof   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Persona Summary Table

| Persona ID | Role Title | Organizational Domain | Primary Product Interaction |
|---|---|---|---|
| **PER-01** | Platform Operator / Executive Gatekeeper | Platform Engineering & Executive Operations | Receives asynchronous webhook alerts for high-risk operations; authorizes or rejects proposals via signed HMAC callback. |
| **PER-02** | Autonomous Worker Agent | DevOps, Infrastructure & AI Swarms | Submits standardized operational proposals programmatically; awaits governance resolution before acting. |
| **PER-03** | Security Guardian | Office of the CISO & Zero-Trust Engineering | Evaluates zero-trust boundaries, IAM privilege escalation, ingress ports, and prompt injection attempts. |
| **PER-04** | Compliance & Legal Arbiter | Corporate Legal & Enterprise Risk | Audits proposals against GDPR Art. 30, HIPAA PHI, SOC 2 Type II, and cross-border transfer constraints. |
| **PER-05** | FinOps Arbiter | Cloud Financial Management | Audits unit economics, budget ceilings (\$500 warning, \$5,000 veto), token burn rates, and savings plan compliance. |
| **PER-06** | SRE Sentinel | Site Reliability & Production Resilience | Evaluates blast radius (0–100 scale), mandates 5% canary stages with 15-minute soak, and verifies automated rollback health probes. |
| **PER-07** | Consensus Arbiter | Core Governance Engine | Synthesizes stakeholder votes, computes composite risk scores, and routes to approval, mitigation, escalation, or veto. |
| **PER-08** | Adaptive Cost Optimizer | Cloud Infrastructure Rightsizing | Intercepts FinOps cost mitigations; restructures payloads using spot/preemptible instances and compute savings plans. |
| **PER-09** | Regulatory Auditor | Internal Audit & Third-Party Assessor | Independently verifies cryptographic SHA-256 ledger chains to prove end-to-end non-repudiation without needing access to engine runtime. |

---

## 4. Product Scope (In-Scope vs. Out-of-Scope)

To guarantee high reliability, zero external infrastructure costs, and seamless deployment on AWS Free Tier, the boundaries of Version 1.0.0 are strictly delineated:

| Functional Area | In-Scope (V1.0 Deliverables) | Out-of-Scope (Explicitly Excluded from V1.0) |
|---|---|---|
| **Deliberation Topology** | Sequential consensus circle (`Security` $\rightarrow$ `Compliance` $\rightarrow$ `FinOps` $\rightarrow$ `SRE` $\rightarrow$ `Arbiter`). | Unstructured parallel chat rooms, unconstrained peer-to-peer agent debate. |
| **Communication Format** | Frozen, strictly typed Pydantic v2 schemas (`StructuredAgentVote`). | Free-form natural language strings between agents, unvalidated JSON payloads. |
| **State Storage & Persistence** | Local file-based JSONL ledger, JSON cache, and JSON suspended state files. | External managed databases (Amazon RDS, DynamoDB, MongoDB, Redis, PostgreSQL). |
| **Concurrency & Mutex** | Cross-platform file locking (`filelock`) for POSIX/Windows filesystem safety. | Distributed locks (Redis Redlock, Apache Zookeeper, Consul), Windows-only `msvcrt` locks. |
| **Network Ingress Gateway** | Lightweight FastAPI + Uvicorn service exposing `/health` and `/resume` endpoints. | Full-fledged GraphQL APIs, gRPC streaming proxies, WebSocket bi-directional channels. |
| **User Interface** | Interactive Rich terminal console demo and auto-generated OpenAPI/Swagger UI (`/docs`). | React/Vue frontend web portals, mobile administrative applications. |
| **HITL Security** | Mandatory HMAC-SHA256 signature verification using `NEMAWASHI_WEBHOOK_SECRET`. | OAuth2/OIDC single sign-on federation, SAML 2.0 integration, multi-factor hardware keys. |
| **LLM Integration** | Google GenAI SDK (`google-genai`) with native `response_schema` binding (`gemini-2.5-flash`). | Deprecated `google-generativeai` SDK, legacy LangChain chains, multi-provider fallbacks (OpenAI, Anthropic). |
| **Execution Autonomy** | Seamless dual-mode execution (live Gemini when API key present; deterministic offline mock when absent). | Mandatory external API connectivity for automated CI/CD testing. |
| **Cloud Infrastructure** | Docker container (`python:3.12-slim`), Docker Compose, AWS EC2 Free Tier (`t2.micro`/`t3.micro`). | Kubernetes cluster deployments, AWS ECS Fargate, distributed multi-region Raft clusters. |

---

## 5. High-Level Functional Capabilities (Product Epics)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Nemawashi Functional Epic Map                         │
├─────────────────────────────┬───────────────────────────────────────────────┤
│ EPIC-01: Deterministic      │ EPIC-02: Pre-Circle Semantic Cache Guardrail  │
│ Policy Guardrails           │ • Vector embedding & cosine similarity lookup │
│ • <5ms hard spend & regex   │ • 24h TTL & enterprise rules hash invalidation│
├─────────────────────────────┼───────────────────────────────────────────────┤
│ EPIC-03: Sequential Multi-  │ EPIC-04: Adaptive Cost Rightsizing Persona    │
│ Stakeholder Consensus       │ • Intercepts budget mitigations               │
│ • Security, Compliance,     │ • Converts on-demand to spot/savings plans    │
│   FinOps, SRE review        │                                               │
├─────────────────────────────┼───────────────────────────────────────────────┤
│ EPIC-05: Bounded Watchdog   │ EPIC-06: Asynchronous HMAC-Secured HITL      │
│ Circuit Breaker             │ • Non-blocking state serialization            │
│ • Hard max_rounds limit     │ • Mandatory HMAC-SHA256 callback gate         │
├─────────────────────────────┴───────────────────────────────────────────────┤
│ EPIC-07: Tamper-Evident SHA-256 Audit Ledger                                │
│ • Forward-secure SHA-256 block chaining with filelock mutex protection      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### EPIC-01: Deterministic Policy Guardrails (Pre-Check Layer)
- Evaluates operational proposals against declarative enterprise rules (`enterprise_rules.json`) prior to any LLM invocation.
- Enforces instant structural vetoes ($<5\text{ms}$) on prohibited actions (e.g., `drop_production_database`, `delete_security_logs`) and target resources matching protected substrings (`prod-primary-db`, `auth-vault`).
- Enforces an absolute spend ceiling: any proposal exceeding $\$5,000.00$ USD direct cost is vetoed immediately.

### EPIC-02: Pre-Circle Semantic Cache Guardrail
- Calculates a deterministic vector embedding of the proposal action type, target resource, and description.
- Evaluates cosine similarity against previously resolved proposals. On matches exceeding $\ge 0.95$, bypasses the multi-agent deliberation circle entirely.
- Enforces strict cache hygiene: entries expire after a 24-hour Time-to-Live (TTL) or when the cryptographic hash of `enterprise_rules.json` changes.
- **Vote Lineage Preservation**: Restores authentic historical `stakeholder_votes` and sets `cache_hit = True` in `AuditRecord`, preserving full non-repudiation and auditability without consensus amnesia. Protected by cross-platform `filelock` mutex locking on `cache.json.lock`.

### EPIC-03: Sequential Multi-Stakeholder Consensus Circle
- Routes proposals through a strictly ordered deliberation circle: Security Guardian $\rightarrow$ Compliance Arbiter $\rightarrow$ FinOps Arbiter $\rightarrow$ SRE Sentinel $\rightarrow$ Consensus Arbiter.
- Downstream stakeholders inherit full visibility into upstream structured votes, preventing contradictory or uncoordinated mitigations.
- Enforces structured memory contracts (`StructuredAgentVote`) with forbidden extra fields and frozen attributes, eliminating free-form conversational chatter.
- **Prompt Injection Defense**: Proposal parameters are encapsulated inside `<untrusted_proposal_data>` XML delimiters with explicit instructions to prevent LLM prompt injection or jailbreaks.

### EPIC-04: Adaptive Cost Rightsizing Persona (Dynamic Branching)
- Intercepts proposals when the FinOps Arbiter issues a `MITIGATE` vote due to cost ceiling breaches ($\ge \$1,000.00$ USD).
- Automatically re-engineers resource parameters to leverage spot/preemptible instances, compute savings plans, and storage volume optimization (gp3), targeting 30%–55% cost reductions.
- Injects the optimized parameters into the proposal and routes into `deliberation_revision_node`, which clears round-scoped votes (`stakeholder_votes: {}`, `stakeholder_map: {}`) for a clean round slate and routes back through `policy_precheck_node` to ensure modified parameters cannot bypass enterprise policy guardrails.

### EPIC-05: Bounded Watchdog Circuit Breaker
- Tracks deliberation iteration rounds (`current_round` initialized at 1).
- Evaluates `current_round > max_rounds` as the very first check in the routing logic.
- If iterations exceed `max_rounds` (default 3), immediately halts the state machine, triggers a structural `CONSENSUS_VETO`, and halts further token consumption.

### EPIC-06: Asynchronous HMAC-Secured HITL Gateway
- Detects high-impact proposals exceeding escalation thresholds: direct cost $\ge \$500.00$ USD, blast radius $\ge 80$, or critical compliance exposure.
- Serializes the complete execution state to local disk (`storage/suspended_states/{proposal_id}.json`), dispatches an asynchronous webhook notification containing deliberation metrics, sets `suspended_for_hitl = True`, and exits the execution thread without blocking.
- Exposes a FastAPI gateway route `POST /resume` enforcing constant-time HMAC-SHA256 signature verification (`hmac.compare_digest`) via `X-Nemawashi-Signature` header or `auth_token` body token.
- **State Integrity & Path Traversal Guards**: Validates proposal IDs against `^[a-zA-Z0-9_-]{1,128}$` and binds cryptographic `_state_hmac` signatures to serialized state files to reject disk-level tampering. Resumes execution directly toward the terminal audit ledger upon verified approval.

### EPIC-07: Tamper-Evident SHA-256 Audit Ledger
- Configured as the strict and sole terminal node preceding graph completion (`END`).
- Acquires a cross-platform file mutex lock (`filelock.FileLock`) before reading the previous block hash or appending the new audit record to `audit_logs/nemawashi_ledger.jsonl`.
- Catches `filelock.Timeout` and converts lock contention into a clean `RuntimeError`, while `verify_ledger_chain()` acquires a shared read lock to prevent partial-line reads during concurrent commits.
- Calculates forward-chained SHA-256 hashes linking index, previous hash, timestamp, proposal ID, verdict, permissions, composite risk, structured votes, mitigations, human approvals, and deliberation rounds.
- Provides a standalone ledger verification utility that mathematically audits the entire JSONL record chain and flags single-byte mutations.

---

## 6. Non-Functional Requirements (NFRs)

### 6.1 Performance & Latency Budgets
- **NFR-01.1 (Pre-Check Response)**: Deterministic policy pre-checks must complete within $< 5\text{ms}$ under standard CPU load.
- **NFR-01.2 (Cache Response)**: Semantic vector cache lookup and cosine similarity evaluation must return in $< 10\text{ms}$.
- **NFR-01.3 (Offline Circle Throughput)**: In offline deterministic rule-based mode, an entire 4-stakeholder deliberation round must complete in $< 1.5\text{s}$.
- **NFR-01.4 (Gateway Latency)**: The FastAPI `POST /resume` callback endpoint must process, verify HMAC signature, resume state, and commit to the ledger in $< 100\text{ms}$ (excluding network transit).

### 6.2 Zero-Trust Security & HMAC Authentication
- **NFR-02.1 (Default-Deny Posture)**: Any proposal that fails to achieve explicit unanimous approval or conditional alignment is denied execution (`execution_permitted = False`).
- **NFR-02.2 (Cryptographic Callback Verification)**: The `/resume` gateway endpoint must reject any callback lacking a valid HMAC-SHA256 signature generated with the shared `NEMAWASHI_WEBHOOK_SECRET`. Signature comparison must use constant-time comparison (`hmac.compare_digest`) to prevent timing attacks.
- **NFR-02.3 (Least Privilege Execution)**: In containerized environments, the application must execute under an unprivileged user (`appuser` with UID 10001) rather than `root`.
- **NFR-02.4 (Injection Immunity)**: Agent system prompts and state channels must strictly isolate untrusted proposal strings from LLM instructions to prevent prompt injection and instruction override attacks.

### 6.3 FinOps Token & Cost Observability
- **NFR-03.1 (Granular Token Accounting)**: Every agent execution turn must calculate prompt tokens, completion tokens, and real-time USD cost based on model-specific pricing grids.
- **NFR-03.2 (Atomic State Channel Aggregation)**: Token and cost accumulators must use custom atomic reducers to prevent race conditions and ensure accurate aggregate reporting.
- **NFR-03.3 (Deliberation Cost Transparency)**: When an operation escalates to a human gatekeeper, the webhook alert payload must display cumulative tokens consumed and accrued USD cost.

### 6.4 Deterministic Offline Autonomy
- **NFR-04.1 (Zero External Dependency CI/CD)**: The test suite and core engine must be capable of executing all unit, integration, and scenario tests offline without requiring live Gemini API keys or external network connectivity.
- **NFR-04.2 (Seamless Dual-Mode Switching)**: When `GEMINI_API_KEY` is present, agents invoke Gemini 2.5 Flash via native structured outputs; when absent, agents seamlessly fall back to deterministic rule-based logic producing 100% schema-compliant votes.

### 6.5 Cloud-Native Docker & AWS Portability
- **NFR-05.1 (Lightweight Container Packaging)**: The production container image must be built from `python:3.12-slim` using multi-stage builds to maintain a final image size $< 350\text{MB}$.
- **NFR-05.2 (Free Tier Resource Compliance)**: The containerized engine must operate reliably within the memory constraints of an AWS EC2 `t2.micro` or `t3.micro` instance (1 vCPU, 1 GB RAM, 8 GB EBS volume).
- **NFR-05.3 (Environment-Driven Directory Configuration)**: All persistent filesystem targets (`NEMAWASHI_AUDIT_LOG_DIR`, `NEMAWASHI_CACHE_DIR`, `NEMAWASHI_STATE_DIR`) must be configurable via environment variables to support clean Docker bind mounts and EBS volume attachments.
- **NFR-05.4 (Cross-Platform Mutex Concurrency)**: All file writes to the shared ledger and cache must utilize POSIX- and Windows-compliant file mutex locking (`filelock`), preventing corruption across multi-threaded or multi-container access.

---

## 7. Compliance, Governance & Regulatory Alignment

The Nemawashi Governance Engine is engineered to satisfy enterprise governance mandates and external regulatory frameworks:

| Regulatory Standard / Control | Statutory Mandate Description | Nemawashi Product Implementation Control |
|---|---|---|
| **GDPR Article 30** | Records of processing activities and data protection oversight. | Compliance Arbiter (PER-04) verifies lawful processing basis; inspects target regions to block unauthorized international cross-border transfers outside EU adequacy borders. |
| **HIPAA Security Rule (45 CFR § 164.312)** | Technical safeguards, access control, audit controls, and data integrity for Protected Health Information (PHI). | Compliance Arbiter verifies PHI isolation, mandates Business Associate Agreements (BAAs), enforces minimum-necessary disclosure, and verifies encryption-at-rest with customer-managed keys. |
| **SOC 2 Type II (Trust Services Criteria CC6.1, CC6.8)** | Access control, operational change authorization, and continuous immutable event logging. | Chained SHA-256 terminal ledger produces continuous, append-only, tamper-evident audit records. Operator approvals require cryptographically verifiable HMAC-SHA256 signatures. |
| **PCI-DSS v4.0 (Requirement 10)** | Log and monitor all access to system components and cardholder data environments. | Every governance turn captures timestamp, proposing agent, target resource, stakeholder votes, composite risk, and hash linkage; raw credit card numbers or unencrypted PAN storage trigger immediate structural veto. |
| **ISO/IEC 27001:2022 (Control A.12.1.2)** | Change management validation and segregation of operational duties. | Prevents autonomous agents from modifying production infrastructure unilaterally; mandates cross-functional consensus and executive approval for high-blast-radius actions. |

---

## 8. Deployment & Release Strategy (AWS Free Tier & CI/CD)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CI/CD & Cloud Deployment Pipeline                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Local Developer Workstation                                              │
│    • Python 3.12 via uv virtual environment                                 │
│    • 66 automated TDD pytest suites executed locally (100% pass)            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                      │ git push origin main                 │
│                                      ▼                                      │
│ 2. GitHub Actions Automated CI Pipeline (ubuntu-latest)                     │
│    • Job 1 (test-and-lint): Python 3.12, uv, full 66-test offline run       │
│    • Job 2 (docker-build-verify): Production container build & verification │
├─────────────────────────────────────────────────────────────────────────────┤
│                                      │ CI Passed                            │
│                                      ▼                                      │
│ 3. Container Build & Packaging                                              │
│    • Production Dockerfile targeting python:3.12-slim                       │
│    • Unprivileged nemawashi system user (UID 10001) security posture        │
│    • Optional image push to Amazon ECR (Elastic Container Registry)         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                      │ Deploy / Pull                        │
│                                      ▼                                      │
│ 4. Target Host: AWS EC2 Free Tier (t2.micro / t3.micro)                    │
│    • 1 vCPU, 1 GB RAM, 8 GB gp2/gp3 EBS Storage Volume                     │
│    • Docker Engine + Docker Compose runtime                                 │
│    • Host Volume Bind Mounts:                                               │
│        - ./audit_logs ──> /app/audit_logs                                   │
│        - ./cache      ──> /app/cache                                        │
│        - ./storage    ──> /app/storage                                      │
│    • Port Mapping: 8000:8000 (FastAPI Gateway: /health, /resume, /docs)     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.1 Continuous Integration Strategy (GitHub Actions)
- **Automated Triggering**: The CI workflow ([`.github/workflows/ci.yml`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/.github/workflows/ci.yml)) triggers on every `push` and `pull_request` targeting `main`.
- **Two-Job Verification Matrix**:
  - **Job 1 (`test-and-lint`)**: Checks out code, sets up Python 3.12 + `uv`, installs dependencies, and runs all 66 automated unit and scenario tests in deterministic offline mode (`GEMINI_API_KEY=""`, `NEMAWASHI_WEBHOOK_SECRET="ci-test-secret-32-bytes-minimum"`).
  - **Job 2 (`docker-build-verify`)**: Builds the production container (`nemawashi-governance-engine:ci`) and executes the 66-test suite directly inside the Linux container, guaranteeing runtime and architecture parity before merge.
- **Zero-Cost Determinism**: All tests run in offline rule-based mode, ensuring zero Gemini API token expenditure during CI runs.
- **Quality Gates**: Any failing unit test, contract regression, or state reducer amnesia failure immediately blocks merging.

### 8.2 Container Packaging Specification
- **Base Image**: `python:3.12-slim` (Debian-based minimal footprint).
- **Security Posture**: Container filesystem is read-only except for designated state mount volumes. Process runs under non-root `appuser`.
- **Port Exposure**: Exposes port `8000` for the FastAPI callback gateway and documentation endpoints.

### 8.3 AWS EC2 Free Tier Operational Model
- **Instance Sizing**: AWS Free Tier eligible `t2.micro` (or `t3.micro` in supported regions): 1 vCPU, 1.0 GiB RAM, 8 GB EBS volume.
- **State Persistence Across Restarts**: Persistent state directories (`audit_logs/`, `cache/`, `storage/`) are mapped directly to host EBS volumes via Docker bind mounts or named volumes. Even if containers are rebuilt or updated, audit history and cache indices remain intact.
- **Resource Constraints Management**: With the Python 3.12 runtime and FastAPI daemon consuming $< 250\text{MB}$ RAM, the application comfortably operates within the 1 GB physical memory ceiling without invoking OOM (Out-of-Memory) killer interventions.

---

*End of Product Requirements Document (`PRD.md`). This document governs functional scope, KPIs, and operational deliverables for Version 1.0.0 of the Nemawashi Enterprise Multi-Agent Governance Engine.*
