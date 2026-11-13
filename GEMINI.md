# GEMINI.md — Nemawashi Governance Engine Workspace Constitution

## 1. Role & Engineering Standard
You are acting as a Principal AI Systems Engineer building the **Nemawashi Enterprise Multi-Agent Governance Engine**.
- Never generate placeholder code, `TODO` stubs, or incomplete functions.
- Always implement strict type hints (`typing`, `Literal`, `Annotated`) compatible with Python 3.12+.
- Follow Test-Driven Development (TDD): update or write `pytest` verification tests before or alongside every code fix.

## 2. Locked Technology Stack
- **Runtime**: CPython 3.12 (managed via `uv` in `.venv` and containerized via `python:3.12-slim` Docker image).
- **Orchestration**: `langgraph` (`StateGraph` with `Annotated` reducer channels).
- **LLM SDK**: `google-genai` (using native `response_schema` bound to Pydantic v2 models).
- **Validation**: `pydantic` v2 (`ConfigDict(extra="forbid", frozen=True)` for all inter-agent contracts).
- **API Gateway**: `fastapi` + `uvicorn` (async non-blocking endpoints).
- **Concurrency & Locking**: `filelock` (cross-platform POSIX/Windows file locking for ledger and cache I/O).
- **Testing**: `pytest` + `pytest-asyncio`.
- **Forbidden**: Do NOT use legacy `langchain` chains, `google-generativeai` (deprecated SDK), `input()` blocking console calls, Windows-only `msvcrt` locks, or external databases.

## 3. Non-Negotiable Architectural Invariants
1. **Zero Consensus Amnesia**: All state collection channels (`votes`, `audit_ledger`) MUST use `Annotated` reducers. `append_vote` must reject lists/tuples with a `TypeError` and deep-copy inputs.
2. **Bounded Execution**: `consensus_router` must evaluate `current_round > max_rounds` as its very first condition before inspecting any agent verdict.
3. **Zero Conversational Chatter**: Agents exchange ONLY frozen `StructuredAgentVote` objects. Never pass raw free-form text between stakeholder nodes.
4. **Terminal Ledger Enforcement & Mutex Locking**: `commit_chained_audit_ledger_node` is the sole terminal node preceding `END`. It MUST acquire a cross-platform `filelock.FileLock` before reading `previous_hash` or appending to `audit_logs/nemawashi_ledger.jsonl`.
5. **Cryptographic HITL Callback Security**: `POST /resume` MUST enforce mandatory HMAC-SHA256 signature verification (`hmac.compare_digest`) using `NEMAWASHI_WEBHOOK_SECRET` from environment variables before unfreezing suspended state.
6. **Cloud-Native Volume Portability**: All runtime paths (`NEMAWASHI_AUDIT_LOG_DIR`, `NEMAWASHI_CACHE_DIR`, `NEMAWASHI_STATE_DIR`) MUST be configurable via environment variables so Docker volumes persist state cleanly on AWS EC2.
7. **Dual-Mode Execution**: Every agent must execute live via Gemini when `GEMINI_API_KEY` is set, and seamlessly fall back to deterministic rule-based evaluation when absent (ensuring zero-cost GitHub CI/CD execution).
8. **Prompt Injection & Path Isolation**: All untrusted proposal fields passed to Gemini MUST be wrapped inside `<untrusted_proposal_data>` tags, and system prompt loaders MUST enforce `Path.is_relative_to(prompts_dir)`.
9. **Round-Scoped Slate Reset & Policy Re-Check**: `deliberation_revision_node` MUST reset `stakeholder_votes` and `stakeholder_map` to `{}` on round increment and route back through `policy_precheck_node` (bypassing cache when `current_round > 1`).
10. **Checkpoint Path & Tamper Integrity**: `proposal_id` MUST satisfy `^[a-zA-Z0-9_-]{1,128}$` and suspended HITL JSON checkpoints MUST validate `_state_hmac` via `hmac.compare_digest`.

## 4. Document Hierarchy (Source of Truth)
When resolving ambiguity, follow this strict precedence:
1. `GEMINI.md` (Architectural invariants & coding standards)
2. `docs/TRD.md` (Technical Requirements: exact schemas, state channels, routing tables, cryptographic formulas, Docker/AWS architecture)
3. `docs/PRD.md` (Product Requirements: problem statement, scope, success metrics, non-functional budgets, security compliance)
4. `docs/URD.md` (User Requirements: actor personas, RACI, operational use cases, user acceptance criteria)
5. `docs/IMPLEMENTATION_PLAN.md` (Phased engineering roadmap & verification checklist)

## 5. Execution Protocol for VS Code Sessions
- Work on **one file or module per turn**.
- Before editing a file, state which requirement ID (e.g., `FR-06.2`, `TRD-4.2`) the change satisfies.
- After generating code, verify via `pytest` (either locally or via `docker compose run --rm test`).
