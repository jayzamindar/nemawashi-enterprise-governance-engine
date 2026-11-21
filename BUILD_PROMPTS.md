# BUILD_PROMPTS.md — Deterministic Remediation & Build Playbook

> Self-contained, ordered engineering prompts (`BUILD-PROMPT-01` through `BUILD-PROMPT-10`) mapping 1:1 to `AUDIT_REMEDIATION_LOG.md` tickets `REM-003` through `REM-011` plus final release verification. Every prompt block below is 100% self-contained, includes the mandatory two-line session bootstrap header, and ends with the **Auto-Commit & Fail-Closed Verification Gate** so it can be copied and pasted into a fresh AI session as-is with zero manual edits. Execute **one prompt per session/turn** in strict order.

---

## `BUILD-PROMPT-01` — CI/CD & Test Harness Stability (`REM-009`)

````markdown
Read `GEMINI.md`, `Enterprise_Blueprint.md`, `PROJECT_MAP.md`, and `AUDIT_REMEDIATION_LOG.md` first to load all project standards.
Execute ONLY this task (`BUILD-PROMPT-01`), follow all TDD/zero-hallucination rules, update `AUDIT_REMEDIATION_LOG.md`, and stop with the 5-line Session Handover Block.

### `BUILD-PROMPT-01` — CI/CD & Test Harness Stability (`REM-009`)
- **Satisfies:** `REM-009` (`Enterprise_Blueprint.md` Phase 1.1)
- **Files to Read:** `GEMINI.md`, `pyproject.toml`, `requirements.txt`, `.github/workflows/ci.yml`, `tests/test_gateway_auth.py`
- **Files to Modify:** `pyproject.toml`, `requirements.txt`, `.github/workflows/ci.yml`, `tests/test_gateway_auth.py` (if fixture teardown causes hang)
- **Requirements & Invariants:**
  1. Add `pytest-timeout`, `pytest-cov`, `ruff`, and `mypy` to `pyproject.toml` (`[project.optional-dependencies].dev`) and `requirements.txt`; standardize away unused `black`/`isort` drift.
  2. Configure `[tool.pytest.ini_options]` with `timeout = 15` and `timeout_method = "thread"`.
  3. Diagnose and fix the `tests/test_gateway_auth.py` hang (zero test deletions or `@pytest.mark.skip`).
  4. Update `.github/workflows/ci.yml` to run `ruff check src/ tests/`, `ruff format --check src/ tests/`, `mypy src/`, and `pytest -q --tb=short --cov=src/nemawashi --cov-report=term:skip-covered --cov-fail-under=90`.
- **Verification Command:**
  ```powershell
  ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/ && pytest -q --tb=short --cov=src/nemawashi --cov-report=term:skip-covered
  ```
- **Handover & Auto-Commit / Fail-Closed Gate:**
  - Mark `REM-009` `[x] DONE` in `AUDIT_REMEDIATION_LOG.md`.
  - **On 100% Pass:** When `pytest` passes at 100% (plus active `ruff`/`mypy` gates), run `git add <explicit_files>` (never `git add -A`), create a descriptive commit referencing `REM-009`, and include the resulting short commit SHA in the 5-line Session Handover Block.
  - **On Any Failure (< 100% Pass):** Do **NOT** run `git commit`. Emit a prominent `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` warning displaying the exact error trace and halt immediately before the next prompt can be run.
````

---

## `BUILD-PROMPT-02` — Strict Frozen Pydantic v2 Contracts (`REM-003`)

````markdown
Read `GEMINI.md`, `Enterprise_Blueprint.md`, `PROJECT_MAP.md`, and `AUDIT_REMEDIATION_LOG.md` first to load all project standards.
Execute ONLY this task (`BUILD-PROMPT-02`), follow all TDD/zero-hallucination rules, update `AUDIT_REMEDIATION_LOG.md`, and stop with the 5-line Session Handover Block.

### `BUILD-PROMPT-02` — Strict Frozen Pydantic v2 Contracts (`REM-003`)
- **Satisfies:** `REM-003` (`Enterprise_Blueprint.md` Phase 2.1)
- **Files to Read:** `GEMINI.md`, `src/nemawashi/core/models.py`, `src/nemawashi/main.py`, `src/nemawashi/agents/optimizer.py`, `tests/test_models.py`, `tests/test_optimizer.py`
- **Files to Modify:** `src/nemawashi/core/models.py`, `src/nemawashi/main.py`, `src/nemawashi/agents/optimizer.py`, `tests/test_models.py`, `tests/test_optimizer.py`
- **Requirements & Invariants:**
  1. Enforce `model_config = ConfigDict(extra="forbid", frozen=True)` on `UsageMetadata`, `AgentProposal`, `Resolution`, `AuditRecord`, and `ResumeProposalRequest`.
  2. Enforce `min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]{1,128}$"` on `AgentProposal.proposal_id`.
  3. Define a strict `ActionType` Literal/Enum or validated allowlist on `AgentProposal.action_type` (compatible with existing test proposals or updated tests).
  4. Replace in-place attribute mutation in `CostOptimizationAgent.optimize` (`optimizer.py`) with `proposal.model_copy(update={...})`.
  5. Replace loose `Dict[str, Any]` in `AuditRecord` with typed `StructuredAgentVote` / frozen `HumanApprovalRecord` models.
  6. Add negative TDD tests asserting `ValidationError` on extra fields, mutation attempts, and invalid `proposal_id` path traversal strings.
- **Verification Command (incremental lint/type check on touched files + full test suite):**
  ```powershell
  ruff check src/nemawashi/core/models.py src/nemawashi/main.py src/nemawashi/agents/optimizer.py tests/test_models.py tests/test_optimizer.py && ruff format --check src/nemawashi/core/models.py src/nemawashi/main.py src/nemawashi/agents/optimizer.py tests/test_models.py tests/test_optimizer.py && mypy src/nemawashi/core/models.py src/nemawashi/main.py src/nemawashi/agents/optimizer.py && pytest -q --tb=short --cov=src/nemawashi --cov-report=term:skip-covered
  ```
- **Handover & Auto-Commit / Fail-Closed Gate:**
  - Mark `REM-003` `[x] DONE` in `AUDIT_REMEDIATION_LOG.md`.
  - **On 100% Pass:** When `pytest` passes at 100% (plus active `ruff`/`mypy` gates on the touched files), run `git add <explicit_files>` (never `git add -A`), create a descriptive commit referencing `REM-003`, and include the resulting short commit SHA in the 5-line Session Handover Block.
  - **On Any Failure (< 100% Pass):** Do **NOT** run `git commit`. Emit a prominent `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` warning displaying the exact error trace and halt immediately before the next prompt can be run.
````

---

## `BUILD-PROMPT-03` — Fail-Closed Policy Catalog & NFKC Normalization (`REM-004`)

````markdown
Read `GEMINI.md`, `Enterprise_Blueprint.md`, `PROJECT_MAP.md`, and `AUDIT_REMEDIATION_LOG.md` first to load all project standards.
Execute ONLY this task (`BUILD-PROMPT-03`), follow all TDD/zero-hallucination rules, update `AUDIT_REMEDIATION_LOG.md`, and stop with the 5-line Session Handover Block.

### `BUILD-PROMPT-03` — Fail-Closed Policy Catalog & NFKC Normalization (`REM-004`)
- **Satisfies:** `REM-004` (`Enterprise_Blueprint.md` Phase 2.2)
- **Files to Read:** `GEMINI.md`, `src/nemawashi/policies/policy_engine.py`, `src/nemawashi/policies/enterprise_rules.json`, `tests/test_policy_engine.py`
- **Files to Modify:** `src/nemawashi/policies/policy_engine.py`, `tests/test_policy_engine.py`
- **Requirements & Invariants:**
  1. Define `EnterpriseRulesConfig(BaseModel)` with `ConfigDict(extra="forbid", frozen=True)` to validate `enterprise_rules.json` (using `encoding="utf-8"`).
  2. Define `CatalogNotFoundError(RuntimeError)` and fail closed (raise `CatalogNotFoundError` or return `passed=False` structural veto) when `enterprise_rules.json` is missing, unreadable, or fails Pydantic validation. Remove the silent partial fallback dictionary.
  3. Normalize `action_type`, `target_resource`, and rule entries with `unicodedata.normalize("NFKC", val).strip().casefold()`.
  4. Add TDD tests for missing/corrupt `enterprise_rules.json` and NFKC fullwidth/whitespace homoglyph bypasses.
- **Verification Command (incremental lint/type check on touched files + full test suite):**
  ```powershell
  ruff check src/nemawashi/policies/policy_engine.py tests/test_policy_engine.py && ruff format --check src/nemawashi/policies/policy_engine.py tests/test_policy_engine.py && mypy src/nemawashi/policies/policy_engine.py && pytest -q --tb=short --cov=src/nemawashi --cov-report=term:skip-covered
  ```
- **Handover & Auto-Commit / Fail-Closed Gate:**
  - Mark `REM-004` `[x] DONE` in `AUDIT_REMEDIATION_LOG.md`.
  - **On 100% Pass:** When `pytest` passes at 100% (plus active `ruff`/`mypy` gates on the touched files), run `git add <explicit_files>` (never `git add -A`), create a descriptive commit referencing `REM-004`, and include the resulting short commit SHA in the 5-line Session Handover Block.
  - **On Any Failure (< 100% Pass):** Do **NOT** run `git commit`. Emit a prominent `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` warning displaying the exact error trace and halt immediately before the next prompt can be run.
````

---

## `BUILD-PROMPT-04` — AI Reasoner Security, Schema Sanitizer & Cache Determinism (`REM-005`)

````markdown
Read `GEMINI.md`, `Enterprise_Blueprint.md`, `PROJECT_MAP.md`, and `AUDIT_REMEDIATION_LOG.md` first to load all project standards.
Execute ONLY this task (`BUILD-PROMPT-04`), follow all TDD/zero-hallucination rules, update `AUDIT_REMEDIATION_LOG.md`, and stop with the 5-line Session Handover Block.

### `BUILD-PROMPT-04` — AI Reasoner Security, Schema Sanitizer & Cache Determinism (`REM-005`)
- **Satisfies:** `REM-005` (`Enterprise_Blueprint.md` Phase 3.1)
- **Files to Read:** `GEMINI.md`, `src/nemawashi/agents/base.py`, `src/nemawashi/core/cache.py`, `tests/test_agents.py`, `tests/test_gemini_schema.py`, `tests/test_cache.py`
- **Files to Modify:** `src/nemawashi/agents/base.py`, `src/nemawashi/core/cache.py`, `tests/test_agents.py`, `tests/test_gemini_schema.py`, `tests/test_cache.py`
- **Requirements & Invariants:**
  1. Add `sanitize_untrusted_text()` stripping XML breakout tags (`</untrusted_proposal_data>`, `<instruction>`, `<system>`, `[SYSTEM]`) and bounding lengths before wrapping inside `<untrusted_proposal_data>`.
  2. Load `GEMINI_MODEL_NAME` from env (default `gemini-2.5-flash`) and enforce `max_output_tokens=8192` in `GenerateContentConfig`.
  3. Implement `clean_gemini_schema()` dereferencing `$defs`/`$ref`, collapsing `anyOf` nullables, and filtering with `ALLOWED_GEMINI_FIELDS`.
  4. Implement `MAX_SESSION_TOKEN_BUDGET` (500,000) and `DAILY_API_COST_LIMIT_USD` ($10.00) circuit breakers falling back to `_evaluate_offline_with_usage`.
  5. Log Gemini exceptions explicitly instead of `except Exception: pass`.
  6. Replace `hash(word)` and `hash(bigram)` in `cache.py` with deterministic `hashlib.sha256` integer indexing.
  7. Add TDD tests for XML breakout sanitization, schema sanitizer, circuit breaker trip, and deterministic cache embeddings.
- **Verification Command (incremental lint/type check on touched files + full test suite):**
  ```powershell
  ruff check src/nemawashi/agents/base.py src/nemawashi/core/cache.py tests/test_agents.py tests/test_gemini_schema.py tests/test_cache.py && ruff format --check src/nemawashi/agents/base.py src/nemawashi/core/cache.py tests/test_agents.py tests/test_gemini_schema.py tests/test_cache.py && mypy src/nemawashi/agents/base.py src/nemawashi/core/cache.py && pytest -q --tb=short --cov=src/nemawashi --cov-report=term:skip-covered
  ```
- **Handover & Auto-Commit / Fail-Closed Gate:**
  - Mark `REM-005` `[x] DONE` in `AUDIT_REMEDIATION_LOG.md`.
  - **On 100% Pass:** When `pytest` passes at 100% (plus active `ruff`/`mypy` gates on the touched files), run `git add <explicit_files>` (never `git add -A`), create a descriptive commit referencing `REM-005`, and include the resulting short commit SHA in the 5-line Session Handover Block.
  - **On Any Failure (< 100% Pass):** Do **NOT** run `git commit`. Emit a prominent `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` warning displaying the exact error trace and halt immediately before the next prompt can be run.
````

---

## `BUILD-PROMPT-05` — Canonical JSON, Anti-Replay & Fail-Closed HMAC (`REM-006`)

````markdown
Read `GEMINI.md`, `Enterprise_Blueprint.md`, `PROJECT_MAP.md`, and `AUDIT_REMEDIATION_LOG.md` first to load all project standards.
Execute ONLY this task (`BUILD-PROMPT-05`), follow all TDD/zero-hallucination rules, update `AUDIT_REMEDIATION_LOG.md`, and stop with the 5-line Session Handover Block.

### `BUILD-PROMPT-05` — Canonical JSON, Anti-Replay & Fail-Closed HMAC (`REM-006`)
- **Satisfies:** `REM-006` (`Enterprise_Blueprint.md` Phase 4.1)
- **Files to Read:** `GEMINI.md`, `src/nemawashi/main.py`, `src/nemawashi/core/graph.py`, `src/nemawashi/audit/ledger.py`, `tests/test_gateway_auth.py`, `tests/test_audit_chain.py`
- **Files to Modify:** `src/nemawashi/main.py`, `src/nemawashi/core/graph.py`, `src/nemawashi/audit/ledger.py`, `tests/test_gateway_auth.py`, `tests/test_audit_chain.py`
- **Requirements & Invariants:**
  1. In `load_suspended_state` (`graph.py`), fail closed (`ValueError`) if `NEMAWASHI_WEBHOOK_SECRET` is set and `_state_hmac` is missing.
  2. Standardize all HMAC and SHA-256 JSON serialization on `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
  3. Upgrade `/resume` HMAC verification (`main.py`) to canonical JSON over `{proposal_id, approved, rationale, issued_at, expires_at, nonce}` with strict `current_time >= expires_at` ($\le 300\text{s}$ TTL) rejection and nonce replay deduplication.
  4. Fail closed at gateway startup (`RuntimeError`) when `ENVIRONMENT=production` and `NEMAWASHI_WEBHOOK_SECRET` is unset, empty, or `"change-me-in-production-32-byte-secret"`.
  5. Ensure all `open()`, `read_text()`, and `write_text()` calls in `graph.py` and `ledger.py` explicitly specify `encoding="utf-8"`.
  6. Add TDD tests for missing `_state_hmac`, expired/replayed `/resume` payloads, and production default secret rejection.
- **Verification Command (incremental lint/type check on touched files + full test suite):**
  ```powershell
  ruff check src/nemawashi/main.py src/nemawashi/core/graph.py src/nemawashi/audit/ledger.py tests/test_gateway_auth.py tests/test_audit_chain.py && ruff format --check src/nemawashi/main.py src/nemawashi/core/graph.py src/nemawashi/audit/ledger.py tests/test_gateway_auth.py tests/test_audit_chain.py && mypy src/nemawashi/main.py src/nemawashi/core/graph.py src/nemawashi/audit/ledger.py && pytest -q --tb=short --cov=src/nemawashi --cov-report=term:skip-covered
  ```
- **Handover & Auto-Commit / Fail-Closed Gate:**
  - Mark `REM-006` `[x] DONE` in `AUDIT_REMEDIATION_LOG.md`.
  - **On 100% Pass:** When `pytest` passes at 100% (plus active `ruff`/`mypy` gates on the touched files), run `git add <explicit_files>` (never `git add -A`), create a descriptive commit referencing `REM-006`, and include the resulting short commit SHA in the 5-line Session Handover Block.
  - **On Any Failure (< 100% Pass):** Do **NOT** run `git commit`. Emit a prominent `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` warning displaying the exact error trace and halt immediately before the next prompt can be run.
````

---

## `BUILD-PROMPT-06` — HITL Concurrency Lock & Dynamic Path Config (`REM-007`)

````markdown
Read `GEMINI.md`, `Enterprise_Blueprint.md`, `PROJECT_MAP.md`, and `AUDIT_REMEDIATION_LOG.md` first to load all project standards.
Execute ONLY this task (`BUILD-PROMPT-06`), follow all TDD/zero-hallucination rules, update `AUDIT_REMEDIATION_LOG.md`, and stop with the 5-line Session Handover Block.

### `BUILD-PROMPT-06` — HITL Concurrency Lock & Dynamic Path Config (`REM-007`)
- **Satisfies:** `REM-007` (`Enterprise_Blueprint.md` Phase 4.2)
- **Files to Read:** `GEMINI.md`, `src/nemawashi/core/engine.py`, `src/nemawashi/core/graph.py`, `src/nemawashi/audit/ledger.py`, `tests/test_gateway_auth.py`
- **Files to Modify:** `src/nemawashi/core/engine.py`, `src/nemawashi/core/graph.py`, `src/nemawashi/audit/ledger.py`, `tests/test_gateway_auth.py`
- **Requirements & Invariants:**
  1. Wrap `load_suspended_state` + ledger commit + `unlink()` in `NemawashiEngine.resume_proposal` inside a per-`proposal_id` `FileLock`.
  2. Route resumed state through `interactive_human_gatekeeper_node` before `commit_chained_audit_ledger_node`.
  3. Resolve `NEMAWASHI_STATE_DIR`, `NEMAWASHI_AUDIT_LOG_DIR`, and `NEMAWASHI_CACHE_DIR` dynamically at call time rather than import-time module constants.
  4. Ensure all `open()`, `read_text()`, and `write_text()` calls in `engine.py` explicitly specify `encoding="utf-8"`.
  5. Add TDD tests for concurrent `/resume` race immunity (using `concurrent.futures.ThreadPoolExecutor` with explicit `future.result(timeout=10)` so lock contention cannot hang the test runner) and dynamic env var path overrides.
- **Verification Command (incremental lint/type check on touched files + full test suite):**
  ```powershell
  ruff check src/nemawashi/core/engine.py src/nemawashi/core/graph.py src/nemawashi/audit/ledger.py tests/test_gateway_auth.py && ruff format --check src/nemawashi/core/engine.py src/nemawashi/core/graph.py src/nemawashi/audit/ledger.py tests/test_gateway_auth.py && mypy src/nemawashi/core/engine.py src/nemawashi/core/graph.py src/nemawashi/audit/ledger.py && pytest -q --tb=short --cov=src/nemawashi --cov-report=term:skip-covered
  ```
- **Handover & Auto-Commit / Fail-Closed Gate:**
  - Mark `REM-007` `[x] DONE` in `AUDIT_REMEDIATION_LOG.md`.
  - **On 100% Pass:** When `pytest` passes at 100% (plus active `ruff`/`mypy` gates on the touched files), run `git add <explicit_files>` (never `git add -A`), create a descriptive commit referencing `REM-007`, and include the resulting short commit SHA in the 5-line Session Handover Block.
  - **On Any Failure (< 100% Pass):** Do **NOT** run `git commit`. Emit a prominent `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` warning displaying the exact error trace and halt immediately before the next prompt can be run.
````

---

## `BUILD-PROMPT-07` — Payload Ceilings, Singleton Engine & Ledger/Cache Quotas (`REM-008`)

````markdown
Read `GEMINI.md`, `Enterprise_Blueprint.md`, `PROJECT_MAP.md`, and `AUDIT_REMEDIATION_LOG.md` first to load all project standards.
Execute ONLY this task (`BUILD-PROMPT-07`), follow all TDD/zero-hallucination rules, update `AUDIT_REMEDIATION_LOG.md`, and stop with the 5-line Session Handover Block.

### `BUILD-PROMPT-07` — Payload Ceilings, Singleton Engine & Ledger/Cache Quotas (`REM-008`)
- **Satisfies:** `REM-008` (`Enterprise_Blueprint.md` Phase 4.3)
- **Files to Read:** `GEMINI.md`, `src/nemawashi/main.py`, `src/nemawashi/core/models.py`, `src/nemawashi/core/cache.py`, `src/nemawashi/audit/ledger.py`
- **Files to Modify:** `src/nemawashi/main.py`, `src/nemawashi/core/models.py`, `src/nemawashi/core/cache.py`, `src/nemawashi/audit/ledger.py`, `tests/test_gateway_auth.py`, `tests/test_cache.py`, `tests/test_audit_chain.py`
- **Requirements & Invariants:**
  1. Add 10MB (10,485,760 bytes) incoming body-size middleware (fast-path `Content-Length` + streaming chunk byte counter returning HTTP 413) and `/ready` probe to `main.py`; reuse a singleton `NemawashiEngine`.
  2. Bound `AgentProposal` string lengths and serialized `parameters` size.
  3. Instantiate `FileLock` per operation in `cache.py` and prune expired (>24h) / excess entries on `store()`.
  4. Implement ledger rotation and retention pruning (`AUDIT_LOG_MAX_SIZE_MB=500`, `AUDIT_LOG_MAX_RETENTION_DAYS=30`) in `ledger.py`.
  5. Add TDD tests for HTTP 413, oversized `AgentProposal` rejection, and cache eviction.
- **Verification Command (incremental lint/type check on touched files + full test suite):**
  ```powershell
  ruff check src/nemawashi/main.py src/nemawashi/core/models.py src/nemawashi/core/cache.py src/nemawashi/audit/ledger.py tests/test_gateway_auth.py tests/test_cache.py tests/test_audit_chain.py && ruff format --check src/nemawashi/main.py src/nemawashi/core/models.py src/nemawashi/core/cache.py src/nemawashi/audit/ledger.py tests/test_gateway_auth.py tests/test_cache.py tests/test_audit_chain.py && mypy src/nemawashi/main.py src/nemawashi/core/models.py src/nemawashi/core/cache.py src/nemawashi/audit/ledger.py && pytest -q --tb=short --cov=src/nemawashi --cov-report=term:skip-covered
  ```
- **Handover & Auto-Commit / Fail-Closed Gate:**
  - Mark `REM-008` `[x] DONE` in `AUDIT_REMEDIATION_LOG.md`.
  - **On 100% Pass:** When `pytest` passes at 100% (plus active `ruff`/`mypy` gates on the touched files), run `git add <explicit_files>` (never `git add -A`), create a descriptive commit referencing `REM-008`, and include the resulting short commit SHA in the 5-line Session Handover Block.
  - **On Any Failure (< 100% Pass):** Do **NOT** run `git commit`. Emit a prominent `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` warning displaying the exact error trace and halt immediately before the next prompt can be run.
````

---

## `BUILD-PROMPT-08` — Multi-Round Revision & Audit Lineage (`REM-010`)

````markdown
Read `GEMINI.md`, `Enterprise_Blueprint.md`, `PROJECT_MAP.md`, and `AUDIT_REMEDIATION_LOG.md` first to load all project standards.
Execute ONLY this task (`BUILD-PROMPT-08`), follow all TDD/zero-hallucination rules, update `AUDIT_REMEDIATION_LOG.md`, and stop with the 5-line Session Handover Block.

### `BUILD-PROMPT-08` — Multi-Round Revision & Audit Lineage (`REM-010`)
- **Satisfies:** `REM-010` (`Enterprise_Blueprint.md` Phase 5.1)
- **Files to Read:** `GEMINI.md`, `src/nemawashi/agents/arbiter.py`, `src/nemawashi/core/graph.py`, `src/nemawashi/audit/ledger.py`, `tests/test_langgraph_routing.py`, `tests/test_e2e_scenarios.py`
- **Files to Modify:** `src/nemawashi/agents/arbiter.py`, `src/nemawashi/audit/ledger.py`, `tests/test_langgraph_routing.py`, `tests/test_e2e_scenarios.py`
- **Requirements & Invariants:**
  1. Fix `ConsensusArbiterAgent.synthesize` to actively evaluate `current_round < max_rounds` and set `requires_revision=True` under well-defined mitigation revision conditions.
  2. Preserve multi-round `state["votes"]` history in `AuditRecord` (or `round_history`) so prior-round votes are not lost after `deliberation_revision_node` resets `stakeholder_votes`.
  3. Add TDD tests verifying multi-round revision, watchdog termination at `max_rounds`, and full multi-round vote lineage in the ledger.
- **Verification Command (incremental lint/type check on touched files + Stage 2 >=90% coverage gate):**
  ```powershell
  ruff check src/nemawashi/agents/arbiter.py src/nemawashi/audit/ledger.py tests/test_langgraph_routing.py tests/test_e2e_scenarios.py && ruff format --check src/nemawashi/agents/arbiter.py src/nemawashi/audit/ledger.py tests/test_langgraph_routing.py tests/test_e2e_scenarios.py && mypy src/nemawashi/agents/arbiter.py src/nemawashi/audit/ledger.py && pytest -q --tb=short --cov=src/nemawashi --cov-report=term:skip-covered --cov-fail-under=90
  ```
- **Handover & Auto-Commit / Fail-Closed Gate:**
  - Mark `REM-010` `[x] DONE` in `AUDIT_REMEDIATION_LOG.md`.
  - **On 100% Pass:** When `pytest` passes at 100% (plus active `ruff`/`mypy`/coverage gates on the touched files), run `git add <explicit_files>` (never `git add -A`), create a descriptive commit referencing `REM-010`, and include the resulting short commit SHA in the 5-line Session Handover Block.
  - **On Any Failure (< 100% Pass):** Do **NOT** run `git commit`. Emit a prominent `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` warning displaying the exact error trace and halt immediately before the next prompt can be run.
````

---

## `BUILD-PROMPT-09` — Documentation, Prompt Registry & Docker Hardening (`REM-011`)

````markdown
Read `GEMINI.md`, `Enterprise_Blueprint.md`, `PROJECT_MAP.md`, and `AUDIT_REMEDIATION_LOG.md` first to load all project standards.
Execute ONLY this task (`BUILD-PROMPT-09`), follow all TDD/zero-hallucination rules, update `AUDIT_REMEDIATION_LOG.md`, and stop with the 5-line Session Handover Block.

### `BUILD-PROMPT-09` — Documentation, Prompt Registry & Docker Hardening (`REM-011`)
- **Satisfies:** `REM-011` (`Enterprise_Blueprint.md` Phase 5.2)
- **Files to Read:** `README.md`, `docs/TRD.md`, `docs/IMPLEMENTATION_PLAN.md`, `Dockerfile`, `src/nemawashi/policies/enterprise_rules.json`, `prompts/`
- **Files to Modify:** `modular_prompt.md` (`NEW FILE`), `README.md`, `docs/TRD.md`, `docs/IMPLEMENTATION_PLAN.md`, `Dockerfile`, `src/nemawashi/policies/enterprise_rules.json` (or `src/nemawashi/policies/policy_engine.py`)
- **Requirements & Invariants:**
  1. Create `modular_prompt.md` indexing all active prompts in `prompts/`.
  2. Resolve missing `prompts/nemawashi_master_prompt.md` and `prompts/cost_optimizer.md` references in `docs/IMPLEMENTATION_PLAN.md`.
  3. Enforce or remove unused `max_blast_radius_auto_approve` in `enterprise_rules.json`.
  4. Update `Dockerfile` `HEALTHCHECK` to probe `http://localhost:8000/health`.
  5. Verify zero dead links and zero `TODO`/`TBD` placeholders across all Markdown files.
- **Verification Command (incremental lint/type check on touched `.py` files if modified + Stage 2 >=90% coverage gate):**
  ```powershell
  ruff check src/nemawashi/policies/policy_engine.py && ruff format --check src/nemawashi/policies/policy_engine.py && mypy src/nemawashi/policies/policy_engine.py && pytest -q --tb=short --cov=src/nemawashi --cov-report=term:skip-covered --cov-fail-under=90
  ```
- **Handover & Auto-Commit / Fail-Closed Gate:**
  - Mark `REM-011` `[x] DONE` in `AUDIT_REMEDIATION_LOG.md`.
  - **On 100% Pass:** When `pytest` passes at 100% (plus active `ruff`/`mypy`/coverage gates on any touched `.py` files), run `git add <explicit_files>` (never `git add -A`), create a descriptive commit referencing `REM-011`, and include the resulting short commit SHA in the 5-line Session Handover Block.
  - **On Any Failure (< 100% Pass):** Do **NOT** run `git commit`. Emit a prominent `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` warning displaying the exact error trace and halt immediately before the next prompt can be run.
````

---

## `BUILD-PROMPT-10` — Final Adversarial Audit & Release Sign-Off

````markdown
Read `GEMINI.md`, `Enterprise_Blueprint.md`, `PROJECT_MAP.md`, and `AUDIT_REMEDIATION_LOG.md` first to load all project standards.
Execute ONLY this task (`BUILD-PROMPT-10`), follow all TDD/zero-hallucination rules, update `AUDIT_REMEDIATION_LOG.md`, and stop with the 5-line Session Handover Block.

### `BUILD-PROMPT-10` — Final Adversarial Audit & Release Sign-Off
- **Satisfies:** `Enterprise_Blueprint.md` Phase 5.3
- **Files to Read:** `GEMINI.md`, `Enterprise_Blueprint.md`, `AUDIT_REMEDIATION_LOG.md`, `PROJECT_MAP.md`
- **Requirements & Invariants:**
  1. Confirm all `REM-001` through `REM-011` tickets in `AUDIT_REMEDIATION_LOG.md` are `[x] DONE`.
  2. Execute the full quiet verification chain and containerized test suite (`docker compose --profile test run --rm test`).
  3. Perform a final zero-hallucination review of `PROJECT_MAP.md` and `Enterprise_Blueprint.md` against the shipped codebase.
- **Verification Command:**
  ```powershell
  ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/ && pytest -q --tb=short --cov=src/nemawashi --cov-report=term:skip-covered --cov-fail-under=90
  ```
- **Handover & Auto-Commit / Fail-Closed Gate:**
  - **On 100% Pass:** When `pytest` passes at 100% (plus full `ruff`/`mypy`/`--cov-fail-under=90` and `docker compose` verification), run `git add <explicit_files>` (never `git add -A`), create a descriptive release sign-off commit referencing `Phase 5.3` / `REM-001`–`REM-011`, and include the resulting short commit SHA in the final 5-line Session Handover Block.
  - **On Any Failure (< 100% Pass):** Do **NOT** run `git commit`. Emit a prominent `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` warning displaying the exact error trace and halt immediately before the next prompt can be run.
````
