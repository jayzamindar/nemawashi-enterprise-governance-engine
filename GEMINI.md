# ==============================================================================
# GEMINI.md — Nemawashi Enterprise Master Handbook
# ==============================================================================
# This document defines the non-negotiable engineering, security, architectural,
# testing, and operational standards for autonomous AI coding agents working in
# the Nemawashi Enterprise Multi-Agent Governance Engine repository.
# ==============================================================================

# ------------------------------------------------------------------------------
# [PROJECT_CONFIGURATION]
# ------------------------------------------------------------------------------
# Project Identifier:        nemawashi-governance-engine
# Target Package Name:       nemawashi
# Root Package Path:         src/nemawashi
# Primary LLM Engine:        Loaded from GEMINI_MODEL_NAME (default: gemini-2.5-flash)
# Fallback Engine:           Deterministic Rule-Based Offline Evaluator (100% CI/CD uptime)
# Runtime Environment:       CPython 3.12+ (managed via uv in .venv, container: python:3.12-slim)
# Orchestration Engine:      langgraph (StateGraph with Annotated monomorphic reducers)
# HTTP API Gateway:          FastAPI + Uvicorn (async non-blocking ingress)
# Default Service Port:      8000
# Max Memory Ceiling:        2048MB (containerized cloud / AWS EC2 target)
# Max Payload Size Ceiling:  10MB (10485760 bytes; HTTP 413 on breach)
# Max Output Token Cap:      8192 tokens (per Gemini request ceiling)
# Max Session Token Budget:  500000 tokens (MAX_SESSION_TOKEN_BUDGET)
# Daily API Cost Limit:      $10.00 USD (DAILY_API_COST_LIMIT_USD)
# Audit Ledger Dir:          NEMAWASHI_AUDIT_LOG_DIR (default: audit_logs/)
# Semantic Cache Dir:        NEMAWASHI_CACHE_DIR (default: cache/)
# Suspended State Dir:       NEMAWASHI_STATE_DIR (default: storage/suspended_states/)
# Webhook / HITL Secret:     NEMAWASHI_WEBHOOK_SECRET
# ------------------------------------------------------------------------------

## 1. Role & Engineering Standard
You are acting as a **Principal AI Systems Architect, Lead SRE, and Staff Security Engineer** building the **Nemawashi Enterprise Multi-Agent Governance Engine**.
- **No Incomplete Implementations:** Never generate placeholder code, `TODO` stubs, `TBD` markers, mock passes, or truncated functions. Implement complete, production-ready logic.
- **Zero-Hallucination Mandate (Code & Documentation):** Never fabricate APIs, library methods, configuration keys, file paths, or architectural claims. Every reference in Python source files or Markdown documentation must be verified against actual repository files.
- **Strict Type Hints:** Enforce explicit type annotations (`typing`, `Literal`, `Annotated`, `Callable`, `TypeVar`) compatible with Python 3.12+ across all modules (`mypy src/` strict clean).
- **Test-Driven Development (TDD):** Author or update `pytest` verification tests before or alongside every code change. Code is complete only when all tests pass cleanly.
- **Anti-Test-Cheating & Verifiable Proof Invariant:**
  - **Zero Test Tampering:** Never delete, comment out, weaken assertions, lower coverage gates, or add `@pytest.mark.skip` / `xfail` to bypass a failing test.
  - **No Self-Mocking:** Mocks/stubs are permitted only for external network/LLM boundaries (e.g., `google-genai` HTTP calls); mocking the internal function, policy check, or guardrail under test is strictly forbidden.
  - **Verbatim Proof Required:** Never fabricate or summarize test results. Every task completion report must include the exact verbatim terminal output line from `pytest` showing passed/failed test counts and code coverage percentage.
- **Cross-Platform UTF-8 File I/O Invariant:** All file reading, writing, logging, schema loading, and subprocess text decoding MUST explicitly specify `encoding="utf-8"` (e.g., `Path.read_text(encoding="utf-8")`, `Path.write_text(..., encoding="utf-8")`, `open(..., encoding="utf-8")`). Relying on OS defaults (`cp1252`) is strictly forbidden.

---

## 2. Locked Technology Stack
- **Runtime:** CPython 3.12+ (managed via `uv` in `.venv` and containerized via `python:3.12-slim` non-root Docker image, UID 10001).
- **Orchestration:** `langgraph` (`StateGraph` with `Annotated` reducer channels).
- **LLM SDK:** `google-genai` (native `response_schema` constrained decoding bound to sanitized Pydantic v2 schemas, `max_output_tokens=8192`, model ID loaded dynamically from `GEMINI_MODEL_NAME`).
- **Validation:** `pydantic` v2 (`ConfigDict(extra="forbid", frozen=True)` for all inter-agent, policy, ledger, and gateway contracts).
- **API Gateway:** `fastapi` + `uvicorn` (async non-blocking endpoints, enforcing a 10MB incoming body-size ceiling returning HTTP 413 on breach).
- **Concurrency & Locking:** `filelock` (cross-platform POSIX/Windows per-operation `FileLock` for ledger, cache, and HITL state mutations).
- **Code Quality & Testing:** `ruff` (lint + format), `mypy` (strict static typing), `pytest` + `pytest-asyncio` + `pytest-timeout` (`timeout = 15`, `timeout_method = "thread"`) + `pytest-cov` ($\ge 90\%$ coverage gate).
- **Forbidden:** Do NOT use legacy `langchain` chains, `google-generativeai` (deprecated SDK), `input()` blocking console calls, Windows-only `msvcrt` locks, Python's randomized `hash()` for persisted embeddings, or external databases.

---

## 3. Non-Negotiable Architectural & Security Invariants

1. **Zero Consensus Amnesia:** All state collection channels (`votes`, `audit_ledger`, `prompt_tokens`, `completion_tokens`, `total_cost_usd`) MUST use `Annotated` reducers. `append_vote` must reject lists/tuples with `TypeError` and deep-copy inputs.
2. **Bounded Execution:** `consensus_router` must evaluate `current_round > max_rounds` as its very first condition before inspecting any agent verdict.
3. **Zero Conversational Chatter:** Agents exchange ONLY frozen `StructuredAgentVote` objects. Never pass raw free-form text between stakeholder nodes.
4. **Terminal Ledger Enforcement & Mutex Locking:** `commit_chained_audit_ledger_node` is the sole terminal node preceding `END`. It MUST acquire a cross-platform per-operation `filelock.FileLock` before reading `previous_hash` or appending to the JSONL ledger. Ledger files must enforce rotation and retention quotas (`AUDIT_LOG_MAX_SIZE_MB=500`, `AUDIT_LOG_MAX_RETENTION_DAYS=30`).
5. **Cryptographic HITL Callback Security & Canonical Serialization:** `POST /resume` MUST enforce mandatory HMAC-SHA256 signature verification (`hmac.compare_digest`) over strict canonical JSON (`json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`) using `NEMAWASHI_WEBHOOK_SECRET`, with anti-replay `issued_at`/`expires_at` ($\le 300\text{s}$ TTL, rejecting `current_time >= expires_at`) and `nonce` deduplication. Production startup must fail closed (`RuntimeError`) if `NEMAWASHI_WEBHOOK_SECRET` is unset, empty, or a default placeholder.
6. **Cloud-Native Volume Portability:** All runtime paths (`NEMAWASHI_AUDIT_LOG_DIR`, `NEMAWASHI_CACHE_DIR`, `NEMAWASHI_STATE_DIR`) MUST be resolved dynamically from environment variables so Docker volumes persist cleanly.
7. **Dual-Mode Execution & Token/Cost Circuit Breakers:** Every agent executes live via Gemini (`GEMINI_MODEL_NAME`, `max_output_tokens=8192`) when `GEMINI_API_KEY` is set, and seamlessly falls back to deterministic rule-based evaluation when absent or upon any API/validation failure (logging the failure) or upon tripping `MAX_SESSION_TOKEN_BUDGET` (500,000) / `DAILY_API_COST_LIMIT_USD` ($10.00).
8. **Prompt Injection Defense & Path Traversal Isolation:** All untrusted proposal fields passed to Gemini MUST be length-bounded, stripped of XML breakout tags (`</untrusted_proposal_data>`, `<instruction>`, `<system>`, `[SYSTEM]`), and enclosed inside `<untrusted_proposal_data>` tags. System prompt loaders MUST enforce `Path.is_relative_to(prompts_dir)`. All modular prompts must be indexed in `modular_prompt.md`.
9. **Round-Scoped Slate Reset & Policy Re-Check:** `deliberation_revision_node` MUST reset `stakeholder_votes` and `stakeholder_map` to `{}` on round increment and route back through `policy_precheck_node` (bypassing cache when `current_round > 1`).
10. **Checkpoint Path & Tamper Integrity:** `proposal_id` MUST satisfy `^[a-zA-Z0-9_-]{1,128}$` at the `AgentProposal` and `ResumeProposalRequest` model boundaries. Suspended HITL JSON checkpoints MUST require and validate `_state_hmac` via `hmac.compare_digest` over canonical JSON when `NEMAWASHI_WEBHOOK_SECRET` is set (fail-closed if missing).
11. **Fail-Closed Deterministic Policy Catalog & NFKC Normalization:** Missing, unreadable, or schema-invalid `enterprise_rules.json` MUST raise `CatalogNotFoundError` / fail closed with a structural VETO (never fall back to partial silent defaults). All policy string matching MUST apply `unicodedata.normalize("NFKC", val).strip().casefold()`.
12. **OpenAPI 3.0 `responseSchema` Sanitization:** Before binding Pydantic schemas to Gemini `response_schema`, dereference `$defs`/`$ref`, collapse `anyOf` nullables to `{"type": "...", "nullable": True}`, and strip unsupported fields using `ALLOWED_GEMINI_FIELDS = {"type", "description", "nullable", "enum", "properties", "items", "required", "title"}`.
13. **10MB HTTP Body Ceiling & Resource Caps:** FastAPI gateway MUST enforce a strict 10MB (10,485,760 bytes) incoming payload limit (fast-path `Content-Length` + streaming chunk byte counter returning HTTP 413). `AgentProposal` text/parameter fields and `SemanticProposalCache` entries must be bounded and expired entries (>24h) pruned.

---

## 4. Document Hierarchy (Source of Truth)
When resolving ambiguity, follow this strict precedence:
1. `GEMINI.md` (Nemawashi Enterprise Master Handbook: architectural invariants & coding standards)
2. `Enterprise_Blueprint.md` (Master production blueprint, DoD, and phased remediation roadmap)
3. `AUDIT_REMEDIATION_LOG.md` & `PROJECT_MAP.md` (Active ticket registry & repository index)
4. `modular_prompt.md` (Centralized prompt registry synchronized with `prompts/`)
5. `docs/TRD.md` (Technical Requirements: schemas, state channels, routing tables, crypto formulas)
6. `docs/PRD.md` (Product Requirements: scope, success metrics, NFRs)
7. `docs/URD.md` (User Requirements: personas, RACI, operational use cases)
8. `docs/IMPLEMENTATION_PLAN.md` (Original engineering roadmap & verification checklist)

---

## 5. Execution Protocol, 3-Strike Circuit Breaker & Session Handover
- **One Ticket Per Turn:** Work on **one `REM-XXX` ticket (or cohesive module) per turn**. Before editing, state which ticket ID and requirement ID it satisfies.
- **3-Strike Anti-Looping Circuit Breaker:** If a `ruff`, `mypy`, `pytest`, or build command fails **3 consecutive times** on the same module or error, HALT immediately, log the exact error trace and root cause in `AUDIT_REMEDIATION_LOG.md`, and escalate to the user.
- **Quiet Verification Chain (Two-Stage Coverage Gate):**
  - *Stage 1 (`BUILD-PROMPT-01`–`07`, early remediation):* Report coverage without failing on the 90% threshold before new tests are written:
    ```powershell
    ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/ && pytest -q --tb=short --cov=src/nemawashi --cov-report=term:skip-covered
    ```
  - *Stage 2 (`BUILD-PROMPT-08`–`10` & CI):* Enforce `--cov-fail-under=90` as a hard blocking gate:
    ```powershell
    ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/ && pytest -q --tb=short --cov=src/nemawashi --cov-report=term:skip-covered --cov-fail-under=90
    ```
- **5-Line Session Handover Block:** At the end of each completed ticket/phase, emit:
  ```markdown
  ### SESSION HANDOVER BLOCK
  1. Completed Ticket(s): REM-XXX (<title>)
  2. Git Status / Modified Files: <file1>, <file2>
  3. Verification Summary: <N> passed, <pct>% coverage (ruff, mypy, pytest clean)
  4. Next Target Ticket: REM-YYY (<title>)
  5. Exact Files to Read Next: <file1>, <file2>
  ```

---

## 8. Deterministic Build Prompt Playbook (`BUILD_PROMPTS.md`)
- **Mandatory Session Bootstrap Header:** Every generated `BUILD-PROMPT-XX` block in `BUILD_PROMPTS.md` MUST be wrapped in a self-contained fenced block and begin with the exact two-line session bootstrap header so it can be copied and executed in a fresh AI session with zero manual edits:
  ```text
  Read `GEMINI.md`, `Enterprise_Blueprint.md`, `PROJECT_MAP.md`, and `AUDIT_REMEDIATION_LOG.md` first to load all project standards.
  Execute ONLY this task (`BUILD-PROMPT-XX`), follow all TDD/zero-hallucination rules, update `AUDIT_REMEDIATION_LOG.md`, and stop with the 5-line Session Handover Block.
  ```
- **Automated Git Commit & Fail-Closed Halt Gate:** Whenever `BUILD_PROMPTS.md` is generated or executed, **every** `BUILD-PROMPT-XX` block MUST end with an **Auto-Commit & Fail-Closed Verification Gate**:
  - **On 100% Pass:** When `pytest` passes at 100% (plus any active `ruff`/`mypy`/coverage gates for that phase), the agent MUST automatically stage the specific modified/created files (`git add <explicit_files>`, never `git add -A`), create a descriptive commit referencing the `REM-XXX` ticket ID, and include the resulting short commit SHA in the 5-line Session Handover Block.
  - **On Any Failure (< 100% Pass):** If `pytest` has any failure/error or an active gate fails, the agent MUST **NOT** run `git commit`. Instead, it MUST emit a prominent `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` warning displaying the exact error trace and halt immediately before the next prompt can be run.
