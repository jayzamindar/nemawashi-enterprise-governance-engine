# AUDIT_REMEDIATION_LOG.md — Nemawashi Governance Engine

> **Audit Scope:** Full-repository architectural, security, schema, orchestration, and documentation-to-code audit of `Nemawashi-Governance-Engine` against `GEMINI.md`, `External_GEMINI.md`, and `External Enterprise_Blueprint.md`.  
> **Audit Mode:** Zero-hallucination forensic review. No `.py` files were modified during this audit run.

---

## Ticket Index

| ID | Severity | Category | Target File(s) | Status |
|---|---|---|---|---|
| `REM-001` | `CRITICAL` | Missing Blueprint | `Enterprise_Blueprint.md` | `[x] DONE` |
| `REM-002` | `HIGH` | Reference Port | `GEMINI.md` | `[x] DONE` |
| `REM-003` | `CRITICAL` | Pydantic | `src/nemawashi/core/models.py`, `src/nemawashi/main.py`, `src/nemawashi/agents/optimizer.py` | `[x] DONE` |
| `REM-004` | `CRITICAL` | Deterministic Guardrail | `src/nemawashi/policies/policy_engine.py`, `src/nemawashi/policies/enterprise_rules.json` | `[ ] OPEN` |
| `REM-005` | `CRITICAL` | Deterministic Guardrail / Resource Ceiling | `src/nemawashi/agents/base.py`, `src/nemawashi/core/cache.py` | `[ ] OPEN` |
| `REM-006` | `CRITICAL` | Crypto/Audit | `src/nemawashi/main.py`, `src/nemawashi/core/graph.py`, `src/nemawashi/audit/ledger.py` | `[ ] OPEN` |
| `REM-007` | `HIGH` | Loop & Self-Healing / Concurrency | `src/nemawashi/core/engine.py`, `src/nemawashi/core/graph.py`, `src/nemawashi/audit/ledger.py` | `[ ] OPEN` |
| `REM-008` | `HIGH` | Resource Ceiling | `src/nemawashi/main.py`, `src/nemawashi/core/models.py`, `src/nemawashi/core/cache.py`, `src/nemawashi/audit/ledger.py` | `[ ] OPEN` |
| `REM-009` | `HIGH` | CI/CD & Test Safety | `pyproject.toml`, `requirements.txt`, `.github/workflows/ci.yml`, `tests/test_gateway_auth.py` | `[x] DONE` |
| `REM-010` | `HIGH` | Loop & Self-Healing | `src/nemawashi/agents/arbiter.py`, `src/nemawashi/core/graph.py`, `src/nemawashi/audit/ledger.py` | `[ ] OPEN` |
| `REM-011` | `MEDIUM` | Documentation Drift | `README.md`, `docs/TRD.md`, `docs/IMPLEMENTATION_PLAN.md`, `Dockerfile`, `prompts/` | `[ ] OPEN` |

---

## Detailed Remediation Tickets

### `REM-001`
- **ID:** `REM-001`
- **Severity:** `CRITICAL`
- **Category:** `Missing Blueprint`
- **Target File(s) & Line(s):** `Enterprise_Blueprint.md` (`NEW FILE`)
- **The Loophole / Ambiguity:** `Nemawashi-Governance-Engine` lacked a dedicated `Enterprise_Blueprint.md` defining the consolidated Definition of Done (DoD), phase-by-phase production backlog, canonical JSON serialization rules, fail-closed catalog requirements, payload/token/RAM ceilings, and CI/CD verification gates.
- **Exact Fix Specification:** Draft `Enterprise_Blueprint.md` at the repository root porting all applicable `[UNIVERSAL CORE]` standards from `External Enterprise_Blueprint.md` and `External_GEMINI.md` tailored to Nemawashi's LangGraph + Gemini + FastAPI + JSONL ledger architecture. *(Draft created during this audit run; formalize and track all `REM-XXX` tickets through it.)*
- **Verification Criteria:** Confirm `Enterprise_Blueprint.md` exists at repository root, contains no `TBD` or `TODO` placeholders, and maps every `REM-XXX` ticket to an actionable phase item.
- **Status:** `[x] DONE`

---

### `REM-002`
- **ID:** `REM-002`
- **Severity:** `HIGH`
- **Category:** `Reference Port`
- **Target File(s) & Line(s):** `GEMINI.md` (lines 1–42)
- **The Loophole / Ambiguity:** The local `GEMINI.md` (42 lines) is missing critical universal engineering and security invariants present in `External_GEMINI.md`:
  1. Anti-test-cheating & verbatim proof invariant (forbidding test deletion, skipped tests, lowered coverage, or self-mocking internal guardrails).
  2. Cross-platform explicit `encoding="utf-8"` file I/O invariant.
  3. Mandatory `pytest-timeout` (`timeout = 15`, `timeout_method = "thread"`) and `pytest-cov` ($\ge 90\%$) gate.
  4. 10MB HTTP incoming payload ceiling (HTTP 413), `maxOutputTokens=8192`, and session token/cost circuit breakers.
  5. OpenAPI 3.0 `responseSchema` sanitization (`$defs`/`$ref` dereference, `anyOf` nullable collapse, `ALLOWED_GEMINI_FIELDS`).
  6. Audit log rotation/retention quotas and `PROJECT_MAP.md` / `modular_prompt.md` governance.
- **Exact Fix Specification:** Merge all applicable `[UNIVERSAL CORE]` invariants from `External_GEMINI.md` into `GEMINI.md` while preserving Nemawashi's LangGraph `StateGraph`, `google-genai`, and JSONL chained ledger stack.
- **Verification Criteria:** Inspect `GEMINI.md` to confirm all 6 missing invariant groups are explicitly codified and consistent with `Enterprise_Blueprint.md`.
- **Status:** `[x] DONE`

---

### `REM-003`
- **ID:** `REM-003`
- **Severity:** `CRITICAL`
- **Category:** `Pydantic`
- **Target File(s) & Line(s):**
  - `src/nemawashi/core/models.py` (lines 39–42, 87–126, 128–165, 167–215)
  - `src/nemawashi/main.py` (lines 42–62)
  - `src/nemawashi/agents/optimizer.py` (lines 25, 51–56)
- **The Loophole / Ambiguity:**
  1. `AgentProposal` (`models.py:90`) uses `ConfigDict(extra="ignore")` and is mutable (`frozen=True` omitted). `CostOptimizationAgent.optimize` (`optimizer.py:51-53`) mutates `optimized` attributes in place.
  2. `AgentProposal.proposal_id` (`models.py:92`) lacks `pattern=r"^[a-zA-Z0-9_-]{1,128}$"`, allowing path-traversal strings like `../evil_path` to be instantiated (violating `GEMINI.md` Invariant #10).
  3. `AgentProposal.action_type` (`models.py:98`) is an unconstrained `str` rather than a validated Enum/Literal or strict pattern, permitting arbitrary unallowlisted action strings.
  4. `Resolution` (`models.py:131`) uses `ConfigDict(extra="ignore")` and is not frozen.
  5. `UsageMetadata` (`models.py:42`) uses `ConfigDict(extra="ignore")` instead of `extra="forbid"`.
  6. `AuditRecord` (`models.py:170`) omits `frozen=True` (drifting from `docs/TRD.md:187`) and uses untyped `Dict[str, Dict[str, Any]]` / `Optional[Dict[str, Any]]`.
  7. `ResumeProposalRequest` (`main.py:42`) omits `model_config = ConfigDict(extra="forbid", frozen=True)`.
- **Exact Fix Specification:**
  1. Set `model_config = ConfigDict(extra="forbid", frozen=True)` on `UsageMetadata`, `AgentProposal`, `Resolution`, `AuditRecord`, and `ResumeProposalRequest`.
  2. Add `min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]{1,128}$"` to `AgentProposal.proposal_id`.
  3. Define a strict `ActionType` Enum/Literal allowlist (or strict regex + catalog validation) for `AgentProposal.action_type`.
  4. Update `CostOptimizationAgent.optimize` (`optimizer.py`) to return `proposal.model_copy(update={...})` instead of mutating fields in place.
  5. Type `AuditRecord.stakeholder_votes` as `Dict[str, StructuredAgentVote]` (or a dedicated frozen `HumanApprovalRecord` model for `human_approval`).
- **Verification Criteria:** Run `pytest tests/test_models.py tests/test_optimizer.py -v` plus new negative tests asserting `ValidationError` on extra fields, mutation attempts, and invalid `proposal_id` patterns.
- **Resolution Notes:** Enforced `ConfigDict(extra="forbid", frozen=True)` on `UsageMetadata`, `AgentProposal`, `Resolution`, `AuditRecord`, and `ResumeProposalRequest`; added `proposal_id` regex (`^[a-zA-Z0-9_-]{1,128}$`) and `ActionType` allowlist on `AgentProposal`; replaced in-place mutation in `CostOptimizationAgent.optimize` with `model_copy(update={...})`; typed `AuditRecord.stakeholder_votes` as `dict[str, StructuredAgentVote]` and `AuditRecord.human_approval` as `HumanApprovalRecord | None`; added negative TDD tests in `tests/test_models.py`, `tests/test_optimizer.py`, and `tests/test_gateway_auth.py`.
- **Status:** `[x] DONE`

---

### `REM-004`
- **ID:** `REM-004`
- **Severity:** `CRITICAL`
- **Category:** `Deterministic Guardrail`
- **Target File(s) & Line(s):**
  - `src/nemawashi/policies/policy_engine.py` (lines 17–97)
  - `src/nemawashi/policies/enterprise_rules.json` (lines 1–23)
- **The Loophole / Ambiguity:**
  1. **Fail-Open Missing Catalog (`policy_engine.py:32-40`):** When `enterprise_rules.json` does not exist, `evaluate_proposal_policies` silently falls back to a stripped-down hardcoded dictionary that omits `disable_cloudtrail_logging`, `modify_security_group_allow_all_ingress_0_0_0_0`, `terminate_payment_gateway_cluster`, `audit-bucket-lock`, and the entire `sensitive_resources` list.
  2. **Unvalidated JSON Schema (`policy_engine.py:43`):** `rules = json.load(f)` is not validated with Pydantic v2, so corrupted or malformed JSON silently degrades via `.get(..., [])`.
  3. **Unicode Homoglyph / Whitespace Bypass (`policy_engine.py:49-61, 83-87`):** Comparisons use `.lower().strip()` without `unicodedata.normalize("NFKC", ...).strip().casefold()`, allowing fullwidth characters (e.g., `ｐｒｏｄ－ｐｒｉｍａｒｙ－ｄｂ`) to bypass substring checks.
- **Exact Fix Specification:**
  1. Define `EnterpriseRulesConfig(BaseModel)` with `model_config = ConfigDict(extra="forbid", frozen=True)` validating all keys in `enterprise_rules.json`.
  2. Raise a custom `CatalogNotFoundError` (or return fail-closed `passed=False` with `CATALOG_MISSING_OR_CORRUPT` violation) when `enterprise_rules.json` is missing, unreadable, or fails schema validation.
  3. Normalize `action_type`, `target_resource`, and rule entries using `unicodedata.normalize("NFKC", val).strip().casefold()`.
- **Verification Criteria:** Run `pytest tests/test_policy_engine.py -v` with added tests for missing/corrupt `enterprise_rules.json` (asserting fail-closed behavior) and NFKC homoglyph bypass attempts.
- **Status:** `[ ] OPEN`

---

### `REM-005`
- **ID:** `REM-005`
- **Severity:** `CRITICAL`
- **Category:** `Deterministic Guardrail`
- **Target File(s) & Line(s):**
  - `src/nemawashi/agents/base.py` (lines 36, 70–82, 102–160)
  - `src/nemawashi/core/cache.py` (lines 71–95)
- **The Loophole / Ambiguity:**
  1. **XML Delimiter Breakout (`base.py:103-119`):** Untrusted `AgentProposal` fields (`action_description`, `target_resource`, `parameters`) are interpolated raw inside `<untrusted_proposal_data>...</untrusted_proposal_data>` without stripping closing tags (`</untrusted_proposal_data>`, `<system>`, `<instruction>`, `[SYSTEM]`) or bounding string length.
  2. **Hardcoded Model & Uncapped Output Tokens (`base.py:36, 124-129`):** `self.model_name = "gemini-2.5-flash"` is hardcoded instead of reading `GEMINI_MODEL_NAME`; `GenerateContentConfig` sets no `max_output_tokens` ceiling (e.g. `8192`).
  3. **No Session Token / Cost Circuit Breaker:** No cumulative token (`MAX_SESSION_TOKEN_BUDGET`) or daily spend (`DAILY_API_COST_LIMIT_USD`) circuit breaker exists to halt runaway Gemini calls.
  4. **Unsanitized `response_schema` (`base.py:127`):** `StructuredAgentVote` is passed directly without OpenAPI 3.0 sanitization (`$defs`/`$ref` dereferencing, `ALLOWED_GEMINI_FIELDS`).
  5. **Silent Exception Swallowing (`base.py:79`):** `except Exception: pass` discards all Gemini API, timeout, and `ValidationError` exceptions without logging or telemetry.
  6. **Non-Deterministic `hash()` in Semantic Cache (`cache.py:83, 88`):** `compute_text_embedding` uses Python's built-in `hash()`, which is randomized per-process via `PYTHONHASHSEED`, invalidating persisted embeddings across restarts.
- **Exact Fix Specification:**
  1. Add a `sanitize_untrusted_text()` helper stripping XML/prompt breakout tags and truncating fields before wrapping in `<untrusted_proposal_data>`.
  2. Load `GEMINI_MODEL_NAME` from environment (default `gemini-2.5-flash`), set `max_output_tokens=8192` in `GenerateContentConfig`, and enforce `MAX_SESSION_TOKEN_BUDGET` / `DAILY_API_COST_LIMIT_USD` circuit breakers.
  3. Implement `clean_gemini_schema()` enforcing `ALLOWED_GEMINI_FIELDS` and `$defs` dereferencing.
  4. Log Gemini exceptions explicitly before falling back to `_evaluate_offline_with_usage`.
  5. Replace `hash(word)` and `hash(bigram)` in `cache.py` with deterministic `int.from_bytes(hashlib.sha256(s.encode("utf-8")).digest()[:8], "big") % dim`.
- **Verification Criteria:** Run `pytest tests/test_agents.py tests/test_gemini_schema.py tests/test_cache.py -v` plus new tests for XML tag breakout stripping, circuit breaker trip, and cross-process deterministic embeddings.
- **Status:** `[ ] OPEN`

---

### `REM-006`
- **ID:** `REM-006`
- **Severity:** `CRITICAL`
- **Category:** `Crypto/Audit`
- **Target File(s) & Line(s):**
  - `src/nemawashi/main.py` (lines 88–100, 119–157)
  - `src/nemawashi/core/graph.py` (lines 115–156)
  - `src/nemawashi/audit/ledger.py` (lines 41–46, 144–154, 278–281)
- **The Loophole / Ambiguity:**
  1. **Fail-Open `_state_hmac` Bypass (`graph.py:143-155`):** In `load_suspended_state`, `if secret and "_state_hmac" in data:` allows an attacker who strips `"_state_hmac"` from the JSON file to completely bypass HMAC verification even when `NEMAWASHI_WEBHOOK_SECRET` is set!
  2. **Delimiter Injection & Missing Anti-Replay on `/resume` (`main.py:88-100`):** `compute_resume_signature` uses colon-delimited string concatenation `f"{proposal_id}:{str(approved).lower()}:{rationale}"` (vulnerable if `rationale` contains `:`) instead of canonical JSON, and lacks `issued_at`, `expires_at` (TTL $\le 300\text{s}$), and `nonce` replay protection.
  3. **Non-Canonical JSON Serialization (`graph.py:117,146` and `ledger.py:144,145,154,279-281`):** Uses `json.dumps(..., sort_keys=True)` without `separators=(",", ":")` and `ensure_ascii=False`.
  4. **No Production Default-Secret Check:** If `ENVIRONMENT=production` and `NEMAWASHI_WEBHOOK_SECRET` is unset or equals `"change-me-in-production-32-byte-secret"`, the gateway does not fail closed at startup.
- **Exact Fix Specification:**
  1. In `load_suspended_state`, when `NEMAWASHI_WEBHOOK_SECRET` is set, **require** `"_state_hmac"` to be present and valid; raise `ValueError` if missing.
  2. Standardize all HMAC and SHA-256 JSON serialization on `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
  3. Upgrade `/resume` signature verification to canonical JSON over `{proposal_id, approved, rationale, issued_at, expires_at, nonce}` with strict `current_time >= expires_at` rejection and nonce deduplication.
  4. Fail closed at gateway startup (`RuntimeError`) if `ENVIRONMENT=production` and `NEMAWASHI_WEBHOOK_SECRET` is empty or matches known placeholder strings.
  5. Ensure all `open()`, `read_text()`, and `write_text()` calls in `graph.py` and `ledger.py` explicitly specify `encoding="utf-8"`.
- **Verification Criteria:** Run `pytest tests/test_gateway_auth.py tests/test_audit_chain.py -v` with new tests proving missing `_state_hmac` raises `ValueError`, expired/replayed `/resume` tokens return `401`/`400`, and production default secret fails closed.
- **Status:** `[ ] OPEN`

---

### `REM-007`
- **ID:** `REM-007`
- **Severity:** `HIGH`
- **Category:** `Loop & Self-Healing`
- **Target File(s) & Line(s):**
  - `src/nemawashi/core/engine.py` (lines 36–74)
  - `src/nemawashi/core/graph.py` (lines 34, 103–157)
  - `src/nemawashi/audit/ledger.py` (lines 22, 94)
- **The Loophole / Ambiguity:**
  1. **TOCTOU Race on `resume_proposal` (`engine.py:48-74`):** Concurrent `/resume` calls for the same `proposal_id` can both read the suspended JSON file before `state_file.unlink()` (line 70) executes, committing duplicate ledger blocks for a single HITL decision.
  2. **Graph Bypass (`engine.py:55`):** `resume_proposal` manually sets dict keys and invokes `commit_chained_audit_ledger_node(state)` directly, bypassing `interactive_human_gatekeeper_node` and `hitl_gatekeeper_routing`.
  3. **Import-Time Path Binding (`graph.py:34`, `ledger.py:22`):** `SUSPENDED_STATES_DIR` and `DEFAULT_LEDGER_PATH` ignore `NEMAWASHI_STATE_DIR` and `NEMAWASHI_AUDIT_LOG_DIR` environment variables, violating `GEMINI.md` Invariant #6.
- **Exact Fix Specification:**
  1. Wrap `load_suspended_state` + ledger commit + `unlink()` inside a per-`proposal_id` `FileLock` in `resume_proposal`.
  2. Route resumed state through `interactive_human_gatekeeper_node` before `commit_chained_audit_ledger_node` (or invoke compiled graph resumption).
  3. Resolve `NEMAWASHI_STATE_DIR`, `NEMAWASHI_AUDIT_LOG_DIR`, and `NEMAWASHI_CACHE_DIR` dynamically via helper functions at call time.
  4. Ensure all `open()`, `read_text()`, and `write_text()` calls in `engine.py` explicitly specify `encoding="utf-8"`.
- **Verification Criteria:** Run `pytest tests/test_gateway_auth.py tests/test_audit_chain.py -v` plus a concurrent `/resume` test (using `concurrent.futures.ThreadPoolExecutor` with explicit `future.result(timeout=10)`) verifying only 1 ledger record is committed and env var path overrides work without monkeypatching module globals.
- **Status:** `[ ] OPEN`

---

### `REM-008`
- **ID:** `REM-008`
- **Severity:** `HIGH`
- **Category:** `Resource Ceiling`
- **Target File(s) & Line(s):**
  - `src/nemawashi/main.py` (lines 35–40, 109–160)
  - `src/nemawashi/core/models.py` (lines 87–126)
  - `src/nemawashi/core/cache.py` (lines 113, 217–260)
  - `src/nemawashi/audit/ledger.py` (lines 22, 49–72, 205–206)
- **The Loophole / Ambiguity:**
  1. **No 10MB Request Body Ceiling (`main.py`):** FastAPI lacks middleware rejecting requests $> 10\text{MB}$ (10,485,760 bytes) via fast-path `Content-Length` and streaming chunk byte counter (HTTP 413).
  2. **Per-Request Graph Recompilation (`main.py:159`):** `resume_deliberation` instantiates `NemawashiEngine()` (recompiling the LangGraph `StateGraph`) on every HTTP request.
  3. **Unbounded `AgentProposal` Payloads (`models.py:92-121`):** No `max_length` on `action_description`, `target_resource`, `proposing_agent`, or size cap on `parameters`.
  4. **Unbounded Cache & Shared Lock Instance (`cache.py:113, 258`):** `self._lock` is shared on the instance rather than instantiated per operation; expired (>24h) entries are never pruned from `semantic_cache.json`.
  5. **Unbounded Ledger Growth (`ledger.py:22, 205`):** `nemawashi_ledger.jsonl` has no size ceiling or rotation/retention policy, risking disk exhaustion on small cloud volumes.
- **Exact Fix Specification:**
  1. Add `ContentSizeLimitMiddleware` (10MB cap, HTTP 413) and `/ready` probe to `main.py`; reuse a module-level/lifespan `NemawashiEngine` singleton.
  2. Add `max_length` constraints to `AgentProposal` string fields and a validator bounding serialized `parameters` size.
  3. Instantiate `FileLock` per operation in `cache.py` and prune expired entries (>24h) + enforce a max-entry cap during `store()`.
  4. Implement ledger rotation/retention quotas (`AUDIT_LOG_MAX_SIZE_MB`, `AUDIT_LOG_MAX_RETENTION_DAYS`) in `ledger.py`.
- **Verification Criteria:** `pytest` tests verifying HTTP 413 on $>10\text{MB}$ payloads, `ValidationError` on oversized `AgentProposal` parameters, and expired cache entry eviction on `store()`.
- **Status:** `[ ] OPEN`

---

### `REM-009`
- **ID:** `REM-009`
- **Severity:** `HIGH`
- **Category:** `Resource Ceiling`
- **Target File(s) & Line(s):**
  - `pyproject.toml` (lines 28–43)
  - `requirements.txt` (lines 24–29)
  - `.github/workflows/ci.yml` (lines 50–72)
  - `tests/test_gateway_auth.py` (lines 22–26)
- **The Loophole / Ambiguity:**
  1. **Test Suite Hang:** Running `.venv\Scripts\pytest.exe tests -v` hung indefinitely in `tests/test_gateway_auth.py` during this audit. `pytest-timeout` is not installed or configured in `pyproject.toml`.
  2. **Missing CI/CD Quality Gates:** `.github/workflows/ci.yml` does not run `ruff check`, `ruff format --check`, `mypy src/`, or `pytest --cov=src/nemawashi --cov-fail-under=90`.
  3. **Toolchain Drift:** `requirements.txt` lists `black`, `isort`, `mypy` while `pyproject.toml` lists `ruff`.
- **Exact Fix Specification:**
  1. Add `pytest-timeout`, `pytest-cov`, `ruff`, and `mypy` to `pyproject.toml` and `requirements.txt`; set `timeout = 15` and `timeout_method = "thread"` in `[tool.pytest.ini_options]`.
  2. Diagnose and resolve the `test_gateway_auth.py` hang (verify `TestClient` / `anyio` teardown).
  3. Update `.github/workflows/ci.yml` to enforce `ruff`, `mypy`, and `--cov-fail-under=90`.
- **Verification Criteria:** Run Stage 1 quiet verification (`ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/ && pytest -q --tb=short --cov=src/nemawashi --cov-report=term:skip-covered`) and observe 100% pass in $<15\text{s}$ per test; `--cov-fail-under=90` is enforced as a hard blocking gate in `BUILD-PROMPT-08` through `BUILD-PROMPT-10` and `.github/workflows/ci.yml`.
- **Resolution Notes:** Added `pytest-timeout`, `pytest-cov`, `pytest-asyncio`, `ruff`, and `mypy` to `pyproject.toml` and `requirements.txt` (removing unused `black`/`isort`); configured `timeout = 15`, `timeout_method = "thread"`, and `asyncio_default_fixture_loop_scope = "function"`; updated `.github/workflows/ci.yml` with `ruff`, `mypy`, and `--cov-fail-under=90`. Diagnosed `tests/test_gateway_auth.py` hang: `TestClient(app)` -> `anyio` -> Windows `asyncio._make_self_pipe()` blocks on loopback `socket._fallback_socketpair()` inside a network-isolated Windows sandbox, and passes in ~1s when loopback sockets are allowed (`pytest-timeout` prevents indefinite hangs). Baseline `ruff` (217 findings) and `mypy src/` (15 errors in 8 files) are tracked for cleanup across `REM-003`–`REM-011`.
- **Status:** `[x] DONE`

---

### `REM-010`
- **ID:** `REM-010`
- **Severity:** `HIGH`
- **Category:** `Loop & Self-Healing`
- **Target File(s) & Line(s):**
  - `src/nemawashi/agents/arbiter.py` (lines 13–111)
  - `src/nemawashi/core/graph.py` (lines 376–389, 445–461)
  - `src/nemawashi/audit/ledger.py` (lines 133, 192)
- **The Loophole / Ambiguity:**
  1. **Dead-End `requires_revision` Logic (`arbiter.py:13-20, 88-96`):** `ConsensusArbiterAgent.synthesize` accepts `current_round` and `max_rounds` but never uses them, and never sets `requires_revision=True`. The `deliberation_revision_node` branch in `consensus_router` (`graph.py:457`) is unreachable unless `cost_optimization_agent_node` runs first.
  2. **Multi-Round Vote Loss in `AuditRecord` (`ledger.py:133, 192`):** Because `deliberation_revision_node` resets `stakeholder_votes` to `{}`, `ledger.py` only records the final round's `stakeholder_votes` and omits the full `state["votes"]` history accumulated by `append_vote`.
- **Exact Fix Specification:**
  1. Define clear deterministic conditions in `ConsensusArbiterAgent.synthesize` for when `CONDITIONAL_ALIGNMENT` sets `requires_revision=True` (bounded by `current_round < max_rounds`).
  2. Record or link multi-round vote history from `state["votes"]` in `AuditRecord` (or `round_history`) so prior-round votes are not lost from the immutable ledger.
- **Verification Criteria:** Run `pytest tests/test_langgraph_routing.py tests/test_e2e_scenarios.py -v` with a new multi-round revision test verifying `requires_revision=True` triggers `deliberation_revision_node`, hits `max_rounds` watchdog cleanly, and preserves multi-round vote lineage in `AuditRecord`.
- **Status:** `[ ] OPEN`

---

### `REM-011`
- **ID:** `REM-011`
- **Severity:** `MEDIUM`
- **Category:** `Documentation Drift`
- **Target File(s) & Line(s):**
  - `docs/IMPLEMENTATION_PLAN.md` (lines 180, 185)
  - `docs/TRD.md` (line 187)
  - `src/nemawashi/policies/enterprise_rules.json` (line 3)
  - `Dockerfile` (line 48)
  - `PROJECT_MAP.md` (`NEW FILE`), `modular_prompt.md` (`NEW FILE`)
- **The Loophole / Ambiguity:**
  1. `docs/IMPLEMENTATION_PLAN.md` references `prompts/nemawashi_master_prompt.md` (line 180) and `prompts/cost_optimizer.md` (line 185), both of which are `MISSING`.
  2. `enterprise_rules.json:3` defines `"max_blast_radius_auto_approve": 75`, which is never read or enforced in `policy_engine.py`.
  3. `Dockerfile:48` healthcheck probes `/docs` instead of `/health` (and `/ready` is absent).
  4. `PROJECT_MAP.md` and `modular_prompt.md` (mandated by `External_GEMINI.md`) do not exist.
- **Exact Fix Specification:**
  1. Create `PROJECT_MAP.md` (~50–70 lines) and `modular_prompt.md` indexing all prompts in `prompts/`.
  2. Either enforce `max_blast_radius_auto_approve` in `policy_engine.py` or remove the dead key from `enterprise_rules.json` (and update `EnterpriseRulesConfig` accordingly).
  3. Update `Dockerfile` `HEALTHCHECK` to probe `http://localhost:8000/health`.
  4. Synchronize `README.md`, `docs/TRD.md`, and `docs/IMPLEMENTATION_PLAN.md` to match actual files and schemas.
- **Verification Criteria:** Verify zero dead file links in `README.md` and `docs/`, `EnterpriseRulesConfig` validates `enterprise_rules.json` with `extra="forbid"`, and `Dockerfile` healthcheck targets `/health`.
- **Status:** `[ ] OPEN`
