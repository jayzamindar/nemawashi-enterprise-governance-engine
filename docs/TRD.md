# Technical Requirements Document (TRD)
## Nemawashi Enterprise Multi-Agent Governance Engine

---

## 1. Document Control & System Architecture

### 1.1 Document Metadata

| Attribute | Specification |
|---|---|
| **Document ID** | `NMW-TRD-2026-V1` |
| **Document Title** | Nemawashi Enterprise Multi-Agent Governance Engine Technical Requirements Document |
| **Version** | `1.0.0` |
| **Status** | `APPROVED` |
| **Classification** | Enterprise Confidential / Technical Specification |
| **Author** | Principal AI Systems Engineer |
| **Runtime Target** | CPython 3.12 (managed via `uv` in `.venv`, containerized via `python:3.12-slim`) |
| **Document Hierarchy** | [`GEMINI.md`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/GEMINI.md) $\rightarrow$ [`docs/TRD.md`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/docs/TRD.md) $\rightarrow$ [`docs/PRD.md`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/docs/PRD.md) $\rightarrow$ [`docs/URD.md`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/docs/URD.md) $\rightarrow$ [`docs/IMPLEMENTATION_PLAN.md`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/docs/IMPLEMENTATION_PLAN.md) |

---

### 1.2 LangGraph State Machine Topology

The governance engine orchestrates multi-agent deliberation via a deterministic LangGraph `StateGraph`. The state machine coordinates proposal ingestion, policy pre-checks, semantic vector cache evaluation, sequential consensus deliberation, dynamic cost rightsizing, loop watchdog circuit breaking, non-blocking asynchronous human checkpoints, and terminal cryptographic ledger commitment.

```mermaid
flowchart TD
    subgraph SwarmLayer["Autonomous Agent Fleet"]
        WorkerAgent["Autonomous Worker Agent (PER-02)"]
    end

    subgraph StateMachine["Nemawashi Sequential StateGraph Architecture"]
        StartNode([START]) --> IntakeNode["intake_proposal_node"]
        IntakeNode --> PolicyPrecheckNode["policy_precheck_node"]
        
        %% Policy Routing
        PolicyPrecheckNode -->|policy_passed == False| ImmediateVetoNode["immediate_policy_veto_node"]
        PolicyPrecheckNode -->|policy_passed == True AND current_round == 1| SemanticCacheNode["semantic_cache_check_node"]
        PolicyPrecheckNode -->|policy_passed == True AND current_round > 1| SecurityNode["security_stakeholder_node"]

        %% Cache Routing
        SemanticCacheNode -->|cache_hit == True| ChainedAuditNode["commit_chained_audit_ledger_node"]
        SemanticCacheNode -->|cache_hit == False| SecurityNode
        
        %% Sequential Consensus Circle
        SecurityNode -->|append_vote| ComplianceNode["compliance_stakeholder_node"]
        ComplianceNode -->|append_vote| FinOpsNode["finops_stakeholder_node"]
        FinOpsNode -->|append_vote| SRENode["reliability_stakeholder_node"]
        SRENode -->|append_vote| ArbiterNode["arbiter_synthesis_node"]
        
        %% Consensus Router (Deterministic Branching)
        ArbiterNode -->|current_round > max_rounds| ImmediateVetoNode
        ArbiterNode -->|verdict == 'CONSENSUS_VETO'| ImmediateVetoNode
        ArbiterNode -->|stakeholder_map['finops'] == 'MITIGATE' AND round < max| CostOptNode["cost_optimization_agent_node"]
        ArbiterNode -->|verdict == 'CONDITIONAL_ALIGNMENT' AND requires_revision AND round < max| RevisionNode["deliberation_revision_node"]
        ArbiterNode -->|verdict == 'HUMAN_IN_THE_LOOP_ESCALATION'| HITLNode["interactive_human_gatekeeper_node"]
        ArbiterNode -->|verdict in ('UNANIMOUS_CONSENSUS', 'CONDITIONAL_ALIGNMENT') AND NOT requires_revision| ChainedAuditNode
        
        %% Adaptive Optimization & Revision Re-entry
        CostOptNode --> RevisionNode
        RevisionNode -->|Round Increment -> Policy Gate| PolicyPrecheckNode
        
        %% Non-Blocking HITL Checkpoint & Suspension
        HITLNode -->|Serialize State & Webhook| EndSuspended([END - Suspended Awaiting /resume])
        
        %% Immediate Veto Funnel
        ImmediateVetoNode --> ChainedAuditNode
        
        %% Terminal Node Enforcement
        ChainedAuditNode -->|append_ledger_record + filelock| EndTerminal([END - Sealed])
    end

    subgraph IngressGateway["FastAPI Ingress Gateway (/resume)"]
        ResumeRoute["POST /resume\n(HMAC-SHA256 Signature Verification)"] -.->|Unfreezes State & Applies Decision| ChainedAuditNode
    end

    WorkerAgent -->|Submit AgentProposal| StartNode
```

---

### 1.3 Deterministic Edge & Routing Table

The state machine strictly enforces deterministic edge transitions. Every condition is evaluated in priority order:

| Source Node | Edge Type | Destination Node | Channel Action / Reducer | Priority & Evaluation Condition |
|---|---|---|---|---|
| `START` | Direct | `intake_proposal_node` | State init | Default entry point from initial proposal submission. |
| `intake_proposal_node` | Direct | `policy_precheck_node` | State update | Evaluates declarative rules from `enterprise_rules.json`. |
| `policy_precheck_node` | Conditional (`policy_routing`) | `immediate_policy_veto_node` | Veto state | **Priority 1**: `policy_passed == False` (prohibited actions, blacklisted regex targets, spend $> \$5,000.00$). |
| `policy_precheck_node` | Conditional (`policy_routing`) | `security_stakeholder_node` | Circle re-entry | **Priority 2**: `policy_passed == True` AND `current_round > 1` (re-evaluating optimizer-revised payload; bypasses cache). |
| `policy_precheck_node` | Conditional (`policy_routing`) | `semantic_cache_check_node` | Cache pre-check | **Priority 3**: `policy_passed == True` AND `current_round == 1` (initial round proposal eligible for cache bypass). |
| `semantic_cache_check_node` | Conditional (`cache_routing`) | `commit_chained_audit_ledger_node` | Cache bypass | **Priority 1**: `cache_hit == True` (cosine $\ge 0.95$, TTL $\le 24\text{h}$, matching rules hash; bypasses multi-agent circle). |
| `semantic_cache_check_node` | Conditional (`cache_routing`) | `security_stakeholder_node` | Circle entry | **Priority 2**: `cache_hit == False` (new proposal requiring full deliberation circle). |
| `security_stakeholder_node` | Direct | `compliance_stakeholder_node` | `append_vote`, `stakeholder_map` | Appends singular `security` vote; sets `stakeholder_map["security"]`. |
| `compliance_stakeholder_node` | Direct | `finops_stakeholder_node` | `append_vote`, `stakeholder_map` | Appends singular `compliance` vote; sets `stakeholder_map["compliance"]`. |
| `finops_stakeholder_node` | Direct | `reliability_stakeholder_node` | `append_vote`, `stakeholder_map` | Appends singular `finops` vote; sets `stakeholder_map["finops"]`. |
| `reliability_stakeholder_node` | Direct | `arbiter_synthesis_node` | `append_vote`, `stakeholder_map` | Appends singular `sre` vote; sets `stakeholder_map["sre"]`. |
| `arbiter_synthesis_node` | Conditional (`consensus_router`) | `immediate_policy_veto_node` | Watchdog veto | **Priority 1 (Circuit Breaker)**: `current_round > max_rounds` OR `resolution.verdict == "CONSENSUS_VETO"`. |
| `arbiter_synthesis_node` | Conditional (`consensus_router`) | `cost_optimization_agent_node` | Adaptive re-route | **Priority 2**: `stakeholder_map.get("finops") == "MITIGATE"` AND `current_round < max_rounds`. |
| `arbiter_synthesis_node` | Conditional (`consensus_router`) | `deliberation_revision_node` | Standard revision | **Priority 3**: `resolution.verdict == "CONDITIONAL_ALIGNMENT"` AND `resolution.requires_revision == True` AND `current_round < max_rounds`. |
| `arbiter_synthesis_node` | Conditional (`consensus_router`) | `interactive_human_gatekeeper_node` | Async checkpoint | **Priority 4**: `resolution.verdict == "HUMAN_IN_THE_LOOP_ESCALATION"` (serializes state to disk; exits cleanly). |
| `arbiter_synthesis_node` | Conditional (`consensus_router`) | `commit_chained_audit_ledger_node` | Consensus seal | **Priority 5**: `resolution.verdict in ("UNANIMOUS_CONSENSUS", "CONDITIONAL_ALIGNMENT")` AND NOT `requires_revision`. |
| `cost_optimization_agent_node` | Direct | `deliberation_revision_node` | Payload update | Rightsizes cloud resources (spot/savings plans) and mutates parameters. |
| `deliberation_revision_node` | Direct | `policy_precheck_node` | Round increment & slate reset | Increments `current_round += 1`, resets `stakeholder_votes: {}` and `stakeholder_map: {}` for a clean round slate, and routes through `policy_precheck_node` to re-verify modified parameters against enterprise policy boundaries. |
| `interactive_human_gatekeeper_node` | Direct | `END` | Non-blocking exit | Thread cleanly terminates awaiting out-of-band operator callback. |
| `immediate_policy_veto_node` | Direct | `commit_chained_audit_ledger_node` | Veto seal | Terminal funnel sealing the veto record in the chained audit ledger. |
| `commit_chained_audit_ledger_node` | Direct (Terminal) | `END` | `append_ledger_record` | Sole terminal node preceding `END`. Acquires `filelock` mutex, seals SHA-256 block, updates vector cache. |

---

## 2. Pydantic v2 Data Contracts & State Channel Reducers

### 2.1 Core Pydantic Models (`src/nemawashi/core/models.py`)

All models enforce strict Pydantic v2 validation. Inter-agent communication is strictly governed by `StructuredAgentVote` with `ConfigDict(extra="forbid", frozen=True)`.

```python
class StructuredAgentVote(BaseModel):
    """Immutable, frozen structured vote emitted by a stakeholder agent.
    
    Prevents context dilution and eliminates arbitrary conversational string commentary.
    Configured as the native Gemini response_schema. Contract is frozen and strictly typed.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    stakeholder_id: Literal["security", "compliance", "finops", "sre"] = Field(
        ..., description="Identifier of the reviewing stakeholder persona."
    )
    vote: Literal["APPROVE", "REJECT", "MITIGATE"] = Field(
        ..., description="Explicit structured verdict."
    )
    risk_tags: List[str] = Field(
        default_factory=list, description="Categorical tags identifying risk vectors."
    )
    mitigation_requirements: List[str] = Field(
        default_factory=list, description="Technical constraints required for execution."
    )
```

```python
class AgentProposal(BaseModel):
    """The operational payload submitted by an autonomous worker agent."""
    proposal_id: str = Field(..., min_length=1)
    proposing_agent: str = Field(..., min_length=1)
    action_type: str = Field(..., min_length=1)
    action_description: str = Field(..., min_length=1)
    target_resource: str = Field(..., min_length=1)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)
    estimated_blast_radius: int = Field(default=0, ge=0, le=100)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
```

```python
class Resolution(BaseModel):
    """Final synthesized consensus decision produced by ConsensusArbiter."""
    proposal_id: str
    verdict: Literal[
        "UNANIMOUS_CONSENSUS",
        "CONDITIONAL_ALIGNMENT",
        "HUMAN_IN_THE_LOOP_ESCALATION",
        "CONSENSUS_VETO",
    ]
    composite_risk_score: int = Field(ge=0, le=100)
    mandatory_mitigations: List[str] = Field(default_factory=list)
    requires_human_approval: bool = False
    requires_revision: bool = False
    summary: str = Field(..., min_length=1)
```

```python
class UsageMetadata(BaseModel):
    """Token consumption and unit economics metrics for an agent turn."""
    model_config = ConfigDict(extra="ignore", frozen=True)

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
```

```python
class AuditRecord(BaseModel):
    """Cryptographically chained block stored in the JSONL audit ledger."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(ge=0)
    timestamp: str
    proposal_id: str
    action_type: str
    verdict: str
    execution_permitted: bool
    composite_risk_score: int = Field(ge=0, le=100)
    stakeholder_votes: Dict[str, Any]
    mitigations: List[str]
    human_approval: Optional[Dict[str, Any]] = None
    deliberation_round: int = Field(ge=1)
    cache_hit: bool = Field(default=False, description="Flag indicating whether this record was served from semantic cache.")
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_cost_usd: float = Field(default=0.0, ge=0.0)
    previous_hash: str = Field(min_length=64, max_length=64)
    record_hash: str = Field(min_length=64, max_length=64)
```

---

### 2.2 LangGraph State Contract (`NemawashiState`) & Channel Reducers

The complete state dictionary consists of **24 strictly typed fields** defined in [`src/nemawashi/core/state.py`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/src/nemawashi/core/state.py):

```python
class NemawashiState(TypedDict, total=False):
    proposal: AgentProposal
    policy_passed: bool
    policy_violations: List[str]
    votes: Annotated[List[StructuredAgentVote], append_vote]
    stakeholder_votes: Dict[str, StructuredAgentVote]
    stakeholder_map: Dict[str, str]
    audit_ledger: Annotated[List[Dict[str, Any]], append_ledger_record]
    prompt_tokens: Annotated[int, accumulate_tokens]
    completion_tokens: Annotated[int, accumulate_tokens]
    total_cost_usd: Annotated[float, accumulate_costs]
    resolution: Optional[Resolution]
    current_round: int
    max_rounds: int
    loop_veto_triggered: bool
    human_approved: Optional[bool]
    execution_permitted: bool
    human_rationale: str
    audit_committed: bool
    audit_record_hash: Optional[str]
    cost_optimization_applied: bool
    optimized_proposal_parameters: Dict[str, Any]
    cached_resolution: Optional[Resolution]
    cache_hit: bool
    suspended_for_hitl: bool
```

### 2.3 Reducer Invariants & Inflation Prevention Rules

1. **`append_vote` (Monomorphic Single-Item Contract)**:
   - **Type Enforcement**: Accepts ONLY a singular `StructuredAgentVote` instance.
   - **Inflation Defense**: Any `list` or `tuple` input raises an immediate `TypeError`. Multi-vote batch injection in a single agent turn is impossible.
   - **Mutation Isolation**: Deep-copies both existing state and incoming vote using `copy.deepcopy()`.
2. **`append_ledger_record`**:
   - Appends dictionary records to `audit_ledger` channel with defensive deep-copying.
3. **`accumulate_tokens`**:
   - Atomically sums integer token counts (`existing + new_tokens`), handling `None` safely.
4. **`accumulate_costs`**:
   - Atomically sums floating point USD cost with deterministic 6-decimal-place rounding (`round((existing or 0.0) + (new_cost or 0.0), 6)`).

---

## 3. Pre-Circle Semantic Cache & Vote Lineage Specification

### 3.1 Vector Embedding & Similarity Mechanics
- **Vector Space**: Deterministic 64-dimensional unit vector computed via word frequency and character bi-gram hashing (`compute_text_embedding`).
- **Normalized Cosine Similarity**:
  $$\text{similarity}(v_1, v_2) = \frac{v_1 \cdot v_2}{\|v_1\| \|v_2\|}$$
- **Cache Hit Gate**: Evaluated proposal matches an entry if:
  1. `entry.action_type == proposal.action_type`
  2. $\text{similarity}(\text{query\_vec}, \text{entry\_vec}) \ge 0.95$

### 3.2 Cache Invalidation & Hygiene Invariants
1. **24-Hour TTL**: Every cache entry stores an ISO 8601 UTC timestamp (`cached_at`). Any entry older than 24 hours ($\Delta t > 86,400\text{s}$) is considered expired and excluded from matching.
2. **Enterprise Rules Hash Matching**: Every cache entry records `rules_hash = SHA256(enterprise_rules.json)`. If `enterprise_rules.json` is modified, the current hash mismatches the cached hash, invalidating the entry to prevent stale policy bypasses.

### 3.3 Vote Lineage Preservation & Cache Concurrency Invariant

```python
class CacheEntry(BaseModel):
    """Persisted cache record containing complete deliberation resolution and vote lineage."""
    model_config = ConfigDict(extra="ignore")

    proposal_id: str
    action_type: str
    action_description: str
    similarity: float = 1.0
    resolution: Resolution
    stakeholder_votes: Dict[str, StructuredAgentVote] = Field(default_factory=dict)
    deliberation_round: int = Field(default=1)
    cached_at: str
    rules_hash: str
```

- **Lineage Retention**: When a resolution is stored in the cache (`SemanticProposalCache.store`), it MUST persist both `resolution` AND `stakeholder_votes` (the complete mapping of the originating structured votes) along with `deliberation_round`.
- **Lineage Restoration**: Upon a cache hit, `semantic_cache_check_node` restores `stakeholder_votes` and the synthesized `stakeholder_map` into the state, marking `cache_hit = True`. When `commit_chained_audit_ledger_node` commits the cache-hit record, `AuditRecord.stakeholder_votes` contains the authentic historical votes and sets `AuditRecord.cache_hit = True`, maintaining audit compliance under SOC 2 and PCI-DSS.
- **Cache Mutex Concurrency**: Both read (`lookup`) and write (`store`) operations on the vector cache acquire a cross-platform lock: `FileLock(f"{cache_path}.lock", timeout=10.0)`, preventing concurrent JSON corruption across parallel worker threads.

---

## 4. Cryptographic Ledger & Cross-Platform Mutex Concurrency (`filelock`)

### 4.1 Cryptographic Hash Formula & Block Lineage

Each block committed to `audit_logs/nemawashi_ledger.jsonl` calculates:

$$\text{record\_hash} = \text{SHA256}(\text{index} + \text{previous\_hash} + \text{timestamp} + \text{proposal\_id} + \text{verdict} + \text{execution\_permitted} + \text{composite\_risk} + \text{votes} + \text{mitigations} + \text{human\_approval} + \text{round})$$

- **Genesis Block**: Block index 0 chains to `GENESIS_HASH = "0" * 64`.
- **Sequential Linkage**: For all $N \ge 1$, $\text{Block}[N].\text{previous\_hash} = \text{Block}[N-1].\text{record\_hash}$.
- **Tamper Detection**: Single-bit modification of any historical record breaks the forward chain and is detected by `verify_ledger_chain()`.

### 4.2 Cross-Platform Mutex Locking (`filelock`)

To prevent race conditions, corrupted writes, and `previous_hash` chain forks under concurrent `/resume` callbacks or multi-container worker threads, `commit_chained_audit_ledger_node` enforces mandatory mutex locking:

```python
lock_path = target_path.with_suffix(".jsonl.lock")
with FileLock(str(lock_path), timeout=10.0):
    # 1. Read the current last record to determine true previous_hash and sequential index
    previous_hash, next_index = _get_last_ledger_hash_and_index(target_path)
    
    # 2. Construct immutable AuditRecord
    audit_entry = AuditRecord(...)
    
    # 3. Append JSON line atomically
    with open(target_path, "a", encoding="utf-8") as f:
        f.write(audit_entry.model_dump_json() + "\n")
```

- **Locking Technology**: `filelock.FileLock` (cross-platform, POSIX `fcntl` on Linux/macOS and `LockFileEx` on Windows).
- **Timeout Budget & Exception Handling**: Maximum 10.0-second lock acquisition timeout (`FileLock(f"{target_path}.lock", timeout=10.0)`). If acquisition times out, `commit_chained_audit_ledger_node` catches `filelock.Timeout` and raises a clean `RuntimeError("Audit ledger lock acquisition timed out")`.
- **Read-Lock Integrity Verification**: `verify_ledger_chain()` also acquires a lock with `timeout=10.0` before scanning the ledger lines, guaranteeing that concurrent ledger append operations never cause partial-line read corruption.

---

## 5. Asynchronous HITL Checkpoint & HMAC-SHA256 FastAPI Gateway (`POST /resume`)

### 5.1 Escalation Triggers & Non-Blocking Checkpointing
Proposals trigger Human-In-The-Loop escalation when:
- `estimated_cost_usd >= 500.00`
- `estimated_blast_radius >= 80`
- `composite_risk_score >= 75`
- Compliance or Security flags an explicit critical statutory risk

When triggered, `interactive_human_gatekeeper_node`:
1. Serializes the complete `NemawashiState` dictionary to `storage/suspended_states/{proposal_id}.json`.
2. Emits an asynchronous webhook payload containing:
   - `proposal_id`, `action_type`, `action_description`, `target_resource`, `estimated_cost_usd`, `estimated_blast_radius`
   - FinOps deliberation metrics: `prompt_tokens`, `completion_tokens`, accrued `total_cost_usd`, and `current_round`
   - Arbiter synthesis rationale and mandatory mitigations
3. Sets `suspended_for_hitl = True` and exits thread execution cleanly to `END`. Blocking console `input()` is completely eliminated.

---

### 5.2 Mandatory HMAC-SHA256 Signature Verification (`POST /resume`)

The FastAPI ingress gateway exposes `POST /resume` to receive operator callback decisions.

#### Security & Authentication Requirements:
- **Shared Secret**: Loaded from environment variable `NEMAWASHI_WEBHOOK_SECRET`.
- **Signature Transmission**: Transmitted via HTTP header `X-Nemawashi-Signature` (with required prefix `sha256=<64_hex_chars>`) or request body field `auth_token` (`<64_hex_chars>`).
- **Signature Formula**:
  $$\text{signature} = \text{HMAC-SHA256}(\text{key}=\text{secret}, \text{msg}=f"\{\text{proposal\_id}\}:\{\text{str(approved).lower()}\}:\{\text{rationale}\}")$$
- **Constant-Time Verification**:
  ```python
  expected_sig = compute_resume_signature(
      proposal_id=req.proposal_id,
      approved=req.approved,
      rationale=req.rationale,
      secret=webhook_secret,
  )

  if not hmac.compare_digest(provided_sig, expected_sig):
      raise HTTPException(
          status_code=status.HTTP_401_UNAUTHORIZED,
          detail="Invalid HMAC-SHA256 callback signature",
      )
  ```
- **Execution Resumption**: Upon successful authentication, the gateway unfreezes state, injects `human_approved` and `human_rationale`, removes the suspended state file from disk, and routes directly into `commit_chained_audit_ledger_node` to seal the verdict in the immutable ledger.

---

### 5.3 State Storage Anti-Tamper & Adversarial Prompt Hardening

1. **Identifier Path-Traversal Validation**:
   - Every proposal identifier entering state storage or gateway resumption must strictly conform to regex `^[a-zA-Z0-9_-]{1,128}$`.
   - Validated via `validate_proposal_id(proposal_id)` in `save_suspended_state`, `load_suspended_state`, and FastAPI schema `ResumeProposalRequest.proposal_id`. Path traversal sequences (`../`, `/etc/`) immediately raise `ValueError` (or HTTP 422/400).
2. **Suspended State File HMAC Protection (`_state_hmac`)**:
   - `save_suspended_state` computes `_state_hmac = HMAC-SHA256(secret, canonical_json)` and attaches it to the persisted state file.
   - `load_suspended_state` verifies this HMAC using `hmac.compare_digest` before deserializing state. Any disk tampering raises `ValueError("Suspended state integrity violation: HMAC mismatch...")`.
3. **Prompt Directory Traversal Containment**:
   - `BaseGovernanceAgent._load_system_prompt` checks that `(prompts_dir / self.prompt_file).resolve().is_relative_to(prompts_dir.resolve())`. Any traversal attempt raises a `ValueError`.
4. **Prompt Injection Framing & Data Delimiting**:
   - In `BaseGovernanceAgent._evaluate_with_gemini`, all proposal parameters are strictly enclosed within `<untrusted_proposal_data>...</untrusted_proposal_data>` blocks.
   - System instructions explicitly mandate that LLMs treat everything within tags strictly as external data, neutralizing embedded prompt overrides or jailbreak payloads.

---

## 6. Containerization & AWS Free Tier Deployment Architecture

### 6.1 Multi-Stage Dockerfile Specification

```dockerfile
# Stage 1: Build & Dependency Resolution
FROM python:3.12-slim AS builder
WORKDIR /build

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY requirements.txt .
RUN uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install --no-cache -r requirements.txt

# Stage 2: Minimal Production Runtime
FROM python:3.12-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/src"

RUN groupadd -g 10001 nemawashi && \
    useradd -u 10001 -g nemawashi -s /bin/bash -m appuser && \
    mkdir -p /app/audit_logs /app/cache /app/storage/suspended_states && \
    chown -R appuser:nemawashi /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:nemawashi . /app

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["uvicorn", "nemawashi.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### 6.2 Docker Compose & Volume Portability (`docker-compose.yml`)

All persistent runtime paths are configurable via environment variables, defaulting to local workspace directories:

```yaml
version: "3.8"

services:
  nemawashi-gateway:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: nemawashi-governance-engine
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - NEMAWASHI_AUDIT_LOG_DIR=${NEMAWASHI_AUDIT_LOG_DIR:-/app/audit_logs}
      - NEMAWASHI_CACHE_DIR=${NEMAWASHI_CACHE_DIR:-/app/cache}
      - NEMAWASHI_STATE_DIR=${NEMAWASHI_STATE_DIR:-/app/storage}
      - NEMAWASHI_WEBHOOK_SECRET=${NEMAWASHI_WEBHOOK_SECRET:?Mandatory secret required}
      - GEMINI_API_KEY=${GEMINI_API_KEY:-}
    volumes:
      - ./audit_logs:/app/audit_logs
      - ./cache:/app/cache
      - ./storage:/app/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
```

---

### 6.3 AWS EC2 Free Tier Infrastructure Blueprint

| AWS Resource | Configuration Specification | Free Tier Compliance |
|---|---|---|
| **Compute Instance** | Amazon EC2 `t2.micro` (or `t3.micro` in modern regions), 1 vCPU, 1.0 GiB RAM | 750 hours/month Free Tier eligible |
| **Operating System** | Amazon Linux 2023 or Ubuntu 24.04 LTS Minimal AMI | Free Tier eligible AMI |
| **Storage Volume** | 8 GB General Purpose SSD (`gp3`), 3,000 IOPS, 125 MB/s | Up to 30 GB EBS included in Free Tier |
| **Networking & Ingress** | Security Group: Ingress TCP 8000 (restricted to corporate API CIDR/VPN), Ingress TCP 22 (SSH keypair), Egress all | Free Tier eligible |
| **Container Registry** | Amazon ECR (Elastic Container Registry) private repository | 500 MB/month storage included |
| **Memory Footprint** | Container idle RSS memory $< 220\text{MB}$; peak deliberation RSS $< 450\text{MB}$ | Operates safely within 1.0 GiB physical RAM without swap thrashing |

---

## 7. Automated Testing & Verification Baseline

The governance engine enforces a locked, comprehensive automated test suite guaranteeing 100% test pass rate across both local CPython 3.12 and containerized Linux execution:

| Test Suite Module | Target Specification | Test Count | Status |
|---|---|---|---|
| [`tests/test_agents.py`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/tests/test_agents.py) | Gemini Structured Outputs, Token Pricing, Fallbacks | 5 | **PASSED** |
| [`tests/test_audit_chain.py`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/tests/test_audit_chain.py) | SHA-256 Ledger, Mutex Locking, FileLock Timeout | 6 | **PASSED** |
| [`tests/test_cache.py`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/tests/test_cache.py) | Cosine Sim, 24h TTL, Rules Invalidation, Vote Lineage | 5 | **PASSED** |
| [`tests/test_e2e_scenarios.py`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/tests/test_e2e_scenarios.py) | End-to-End Enterprise Governance Scenarios | 5 | **PASSED** |
| [`tests/test_gateway_auth.py`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/tests/test_gateway_auth.py) | HMAC Callback, State HMAC, Path Traversal, Prompts | 9 | **PASSED** |
| [`tests/test_gemini_schema.py`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/tests/test_gemini_schema.py) | Gemini Pydantic Schema Compatibility | 2 | **PASSED** |
| [`tests/test_langgraph_routing.py`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/tests/test_langgraph_routing.py) | LangGraph State Transitions, Routing, Round Slate Reset | 10 | **PASSED** |
| [`tests/test_models.py`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/tests/test_models.py) | Pydantic v2 Frozen Contracts & Validation | 9 | **PASSED** |
| [`tests/test_optimizer.py`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/tests/test_optimizer.py) | Cloud Resource Rightsizing & Spend Optimization | 3 | **PASSED** |
| [`tests/test_policy_engine.py`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/tests/test_policy_engine.py) | Declarative Rules Engine & Policy Violations | 5 | **PASSED** |
| [`tests/test_state_reducers.py`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/tests/test_state_reducers.py) | Monomorphic Reducers & Amnesia Prevention | 7 | **PASSED** |
| **Total Test Baseline** | **Comprehensive Engine Verification** | **66** | **100% PASS** |

---

*End of Technical Requirements Document (`TRD.md`). This document serves as the technical source of truth for all implementations across the Nemawashi Governance Engine.*
