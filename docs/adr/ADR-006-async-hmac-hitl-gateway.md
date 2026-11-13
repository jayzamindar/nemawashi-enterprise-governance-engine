# ADR-006: Asynchronous Non-Blocking HITL Checkpointing & HMAC-SHA256 Ingress Gateway

## Status
**ACCEPTED** (2026-11-12)

## Context
Enterprise governance architectures require human executive intervention (Human-In-The-Loop / HITL) whenever operational spend exceeds financial limits (e.g., $\ge \$500.00$), blast radius is severe ($\ge 80/100$), or statutory compliance boundaries are flagged.

Early multi-agent governance prototypes implemented HITL using synchronous CLI prompts (`input()`). This introduced severe production architectural anti-patterns:
1. **Thread Starvation & Hanging Execution**: Blocking CLI calls freeze the Python execution thread, preventing cloud-native autoscaling, container health check probes, and concurrent proposal processing.
2. **Volatile Memory Loss**: If the host process restarts, times out, or crashes during operator contemplation, the in-flight state is obliterated without recovery.
3. **Unauthenticated Callback Risk**: Naive webhook callbacks lacking cryptographic authentication expose enterprise infrastructure to unauthorized execution triggers and replay tampering.

## Decision
We eliminated synchronous `input()` and replaced it with a **non-blocking asynchronous checkpoint architecture** paired with an **HMAC-SHA256 authenticated FastAPI ingress gateway**:
1. **Non-Blocking Disk Checkpointing**: When `interactive_human_gatekeeper_node` triggers, the engine serializes the complete `NemawashiState` dictionary to `/app/storage/suspended_states/{proposal_id}.json`, emits an out-of-band notification event, marks `suspended_for_hitl = True`, and cleanly terminates execution to `END`.
2. **FastAPI Ingress Gateway (`POST /resume`)**: Exposes an async endpoint where human operators submit decisions (`approved: bool`, `rationale: str`).
3. **Mandatory HMAC-SHA256 Authentication**:
   - Every callback must provide an HMAC-SHA256 cryptographic signature via the `X-Nemawashi-Signature` HTTP header (or fallback `auth_token` body field).
   - The gateway validates the signature using `hmac.compare_digest` against `NEMAWASHI_WEBHOOK_SECRET` in constant time, preventing timing side-channel attacks.
   - Missing or invalid signatures immediately fail closed with `HTTP 401 Unauthorized`.
4. **Resumption & Terminal Sealing**: Upon verification, the engine unfreezes state, injects the operator rationale, removes the checkpoint file from disk, and routes directly into `commit_chained_audit_ledger_node` to seal the decision into the immutable SHA-256 ledger.

## Consequences

### Positive
- **Cloud-Native Concurrency**: Worker threads exit immediately upon escalation; zero blocking calls occur inside containers.
- **Durable State Resilience**: Suspended proposals survive host restarts and can be resumed days later without context loss.
- **Cryptographic Security**: Eliminates unauthorized external execution injection and tamper vectors on critical infrastructure actions.

### Negative
- **Operational Storage Management**: Requires persistent storage volumes (`/app/storage/suspended_states`) mapped in Docker Compose to preserve state files across container lifecycles.
