# Master Production Elevation Blueprint & Engineering Plan (`Enterprise_Blueprint.md`)

> **Consolidated Architecture & Backlog Notice:** This document serves as the unified **Master Production Elevation Blueprint**, **Living Engineering Plan**, and **Active Build Backlog** for `nemawashi-governance-engine`. All architectural milestones, security invariants, task checklists, and verification gates are maintained herein alongside [`GEMINI.md`](GEMINI.md) and [`AUDIT_REMEDIATION_LOG.md`](AUDIT_REMEDIATION_LOG.md).

**Project:** Nemawashi Enterprise Multi-Agent Governance Engine (`nemawashi-governance-engine`)  
**Lead Architect:** Principal AI Systems Architect, Lead SRE & Staff Security Engineer  
**Status:** Living Engineering Plan & Active Remediation Backlog  
**Target Standard:** Tier-1 Enterprise Production Grade  
**Runtime:** CPython 3.12+ (managed via `uv` in `.venv`, containerized via `python:3.12-slim`)  
**Orchestration:** `langgraph` (`StateGraph` with `Annotated` monomorphic reducers)  
**LLM SDK:** `google-genai` (`response_schema` constrained decoding) + Deterministic Offline Fallback  
**API Gateway:** `fastapi` + `uvicorn` (async non-blocking ingress)

---

## 1. Architectural Tenets & Definition of Done (DoD)

Every module and remediation ticket in `nemawashi-governance-engine` must satisfy the following **10 Architectural Tenets (DoD)**:

1. **Bounded Multi-Agent Deliberation & Zero Consensus Amnesia:**
   - LangGraph `StateGraph` channels (`votes`, `audit_ledger`, `prompt_tokens`, `completion_tokens`, `total_cost_usd`) MUST use `Annotated` reducers. `append_vote` must reject collections (`list`, `tuple`) with `TypeError` and deep-copy inputs.
   - `consensus_router` MUST evaluate `current_round > max_rounds` as its first condition before inspecting any verdict.
   - `deliberation_revision_node` MUST reset `stakeholder_votes` and `stakeholder_map` to `{}` on round increment and route back through `policy_precheck_node` (bypassing cache when `current_round > 1`).

2. **Strict Pydantic v2 Contracts & Enum/Schema Discipline:**
   - 100% of inter-agent, policy, ledger, and gateway data contracts (`StructuredAgentVote`, `AgentProposal`, `Resolution`, `UsageMetadata`, `ModelPricing`, `AuditRecord`, `ResumeProposalRequest`) MUST enforce `ConfigDict(extra="forbid", frozen=True)`.
   - `proposal_id` MUST enforce `^[a-zA-Z0-9_-]{1,128}$` at the model boundary.
   - `AgentProposal.action_type` MUST validate against an explicit `ActionType` allowlist/pattern.

3. **Deterministic Guardrails & Fail-Closed Policy Catalogs:**
   - Security, Compliance, FinOps, and SRE policy pre-checks MUST execute deterministically prior to any LLM invocation.
   - Missing, unreadable, or schema-invalid `enterprise_rules.json` MUST raise `CatalogNotFoundError` / fail closed with a structural VETO—silent partial defaults are strictly forbidden.
   - All inbound action/target strings evaluated by deterministic rules MUST undergo Unicode NFKC normalization and `.strip().casefold()`.

4. **Prompt Injection Defense & Path Traversal Isolation:**
   - All untrusted `AgentProposal` fields passed to Gemini MUST be length-bounded, stripped of XML breakout tags (`</untrusted_proposal_data>`, `<instruction>`, `<system>`, `[SYSTEM]`), and enclosed inside `<untrusted_proposal_data>` tags.
   - Prompt file loaders MUST enforce `Path.is_relative_to(prompts_dir)`.
   - All modular system prompts MUST be indexed in `modular_prompt.md` and synchronized with `prompts/`.

5. **OpenAPI 3.0 `responseSchema` Sanitization & Token/Cost Circuit Breakers:**
   - Before passing `response_schema` to Gemini, dereference `$defs`/`$ref`, collapse `anyOf` nullables to `{"type": "...", "nullable": True}`, and strip unsupported fields using `ALLOWED_GEMINI_FIELDS`.
   - Load model ID dynamically from `GEMINI_MODEL_NAME` (default `gemini-2.5-flash`), cap `max_output_tokens=8192`, log all Gemini exceptions before deterministic offline fallback, and enforce `MAX_SESSION_TOKEN_BUDGET=500000` / `DAILY_API_COST_LIMIT_USD=10.00` circuit breakers.

6. **Cryptographic Integrity, Canonical Serialization & Anti-Replay:**
   - All HMAC-SHA256 signatures (`/resume` callbacks, `_state_hmac` checkpoints) and SHA-256 audit ledger hashes MUST serialize payloads using strict canonical JSON:
     `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`
   - Verification MUST use `hmac.compare_digest()`. Suspended state loading MUST fail closed if `_state_hmac` is missing when `NEMAWASHI_WEBHOOK_SECRET` is configured.
   - `/resume` callbacks MUST enforce anti-replay protection (`issued_at`, `expires_at` TTL $\le 300\text{s}$ rejecting `current_time >= expires_at`, and `nonce` deduplication). Production startup MUST fail closed (`RuntimeError`) if `NEMAWASHI_WEBHOOK_SECRET` is unset, empty, or a default placeholder.

7. **Cross-Platform Concurrency, Dynamic Volume Portability & UTF-8 I/O:**
   - All file I/O MUST specify `encoding="utf-8"`.
   - Per-operation `filelock.FileLock(timeout=10.0)` MUST wrap ledger commits, cache mutations, and HITL `resume_proposal` load-commit-unlink transitions.
   - All runtime paths (`NEMAWASHI_AUDIT_LOG_DIR`, `NEMAWASHI_CACHE_DIR`, `NEMAWASHI_STATE_DIR`) MUST resolve dynamically from environment variables.

8. **Resource Ceilings, 10MB Payload Defense & Cache/Ledger Quotas:**
   - FastAPI gateway MUST enforce a strict **10MB (10,485,760 bytes)** incoming body limit (fast-path `Content-Length` + streaming chunk byte counter returning HTTP 413) and reuse a singleton `NemawashiEngine`.
   - `SemanticProposalCache` MUST use deterministic `hashlib.sha256` embeddings (never Python `hash()`) and prune expired (>24h) entries.
   - JSONL audit logs MUST enforce rotation and retention quotas (`AUDIT_LOG_MAX_SIZE_MB=500`, `AUDIT_LOG_MAX_RETENTION_DAYS=30`).

9. **Anti-Test-Cheating, `pytest-timeout` & CI/CD Quality Gates:**
   - `pyproject.toml` MUST enforce `pytest-timeout` (`timeout = 15`, `timeout_method = "thread"`), `ruff`, `mypy`, and `pytest-cov` ($\ge 90\%$ coverage gate).
   - Zero test tampering (no skipped/weakened tests, no self-mocking of internal guardrails). Mocks are restricted to external network/LLM boundaries.
   - **Auto-Commit & Fail-Closed Verification Gate:** Every `BUILD-PROMPT-XX` execution MUST pass 100% of `pytest` and active `ruff`/`mypy`/coverage gates before staging explicit files (`git add <explicit_files>`, never `git add -A`) and committing with the `REM-XXX` ticket ID; any failure MUST block `git commit` and emit `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` with the exact error trace.

10. **Cross-Document Synchronization & Zero-Drift Governance:**
    - `README.md`, `PROJECT_MAP.md`, `modular_prompt.md`, `docs/TRD.md`, `docs/PRD.md`, `docs/URD.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/DEPLOYMENT_AWS.md`, `docs/DEPLOYMENT_AZURE.md`, `Dockerfile`, `docker-compose.yml`, and `docker-compose.prod.yml` MUST remain 100% synchronized with the shipped codebase, with zero dead links or `TODO`/`TBD` placeholders.
    - `README.md` MUST serve as a **100% hyperlinked Master Navigation Hub** with clickable relative Markdown links (`[Title](path/to/file.md)`) for every governance, specification, audit, deployment, container/CI, and ADR document in the repository.

---

## 2. Phase-by-Phase Production & Remediation Roadmap

### Phase 0: Governance, Constitution & Playbook Foundation
- [x] **0.1 Forensic Audit & Remediation Log:** Author `AUDIT_REMEDIATION_LOG.md` mapping all security, schema, orchestration, and drift findings to sequential `REM-XXX` tickets.
- [x] **0.2 Master Blueprint Creation (`REM-001`):** Finalize `Enterprise_Blueprint.md` tailored to `Nemawashi-Governance-Engine`.
- [x] **0.3 Constitution Synchronization (`REM-002`):** Upgrade `GEMINI.md` with `[PROJECT_CONFIGURATION]`, UTF-8 I/O, anti-test-cheating, circuit breakers, OpenAPI 3.0 sanitization, and 3-strike handover rules.
- [x] **0.4 Repository Map & Build Playbook:** Create `PROJECT_MAP.md` and `BUILD_PROMPTS.md` (`BUILD-PROMPT-01` through `BUILD-PROMPT-10`).
- [x] **0.10 Deterministic Build Prompt Playbook (`BUILD_PROMPTS.md`):** Every `BUILD-PROMPT-XX` block in `BUILD_PROMPTS.md` MUST be wrapped in a self-contained fenced block, begin with the mandatory two-line session bootstrap header (`Read GEMINI.md, Enterprise_Blueprint.md, PROJECT_MAP.md, and AUDIT_REMEDIATION_LOG.md first to load all project standards.` / `Execute ONLY this task (BUILD-PROMPT-XX), follow all TDD/zero-hallucination rules, update AUDIT_REMEDIATION_LOG.md, and stop with the 5-line Session Handover Block.`), and end with the **Auto-Commit & Fail-Closed Verification Gate** (on 100% pass of `pytest` and active `ruff`/`mypy`/coverage gates: `git add <explicit_files>` + descriptive `REM-XXX` commit + short SHA in Handover Block; on any failure: **DO NOT** run `git commit`, emit `🚨 GATE FAILURE — HUMAN REVIEW REQUIRED` with the exact error trace, and halt immediately) so every prompt is 100% self-contained and fail-closed when run in a fresh session.

### Phase 1: CI/CD & Test Harness Stability
- [x] **1.1 Test Timeout, Coverage & Lint Gates (`REM-009` / `BUILD-PROMPT-01`):** Add `pytest-timeout` (`timeout = 15`, `timeout_method = "thread"`), `pytest-cov`, `ruff`, and `mypy` to `pyproject.toml`, `requirements.txt`, and `.github/workflows/ci.yml`; diagnose and fix the `tests/test_gateway_auth.py` hang.

### Phase 2: Pydantic v2 Contracts & Deterministic Policy Hardening
- [x] **2.1 Strict Frozen Pydantic v2 Contracts (`REM-003` / `BUILD-PROMPT-02`):** Enforce `ConfigDict(extra="forbid", frozen=True)`, `proposal_id` regex, `ActionType` allowlist, and `model_copy` immutability across `models.py`, `main.py`, and `optimizer.py`.
- [x] **2.2 Fail-Closed Policy Catalog & NFKC Normalization (`REM-004` / `BUILD-PROMPT-03`):** Add `EnterpriseRulesConfig` validation, `CatalogNotFoundError` fail-closed handling, and NFKC + `casefold()` normalization in `policy_engine.py`.

### Phase 3: AI Reasoner Security, Schema Sanitization & Deterministic Cache
- [x] **3.1 Prompt Injection, Schema Sanitizer, Circuit Breakers & Cache Hash (`REM-005` / `BUILD-PROMPT-04`):** Strip XML breakout tags, enforce field length caps, load `GEMINI_MODEL_NAME` dynamically, cap `max_output_tokens=8192`, add OpenAPI 3.0 `clean_gemini_schema()`, add token/cost circuit breakers, log exceptions, and replace `hash()` with `hashlib.sha256` in `cache.py`.

### Phase 4: Cryptographic Integrity, Concurrency & Resource Ceilings
- [x] **4.1 Canonical JSON, Anti-Replay & Fail-Closed HMAC (`REM-006` / `BUILD-PROMPT-05`):** Enforce canonical JSON (`separators=(',', ':'), ensure_ascii=False`), require `_state_hmac` unconditionally when secret is set, add `/resume` TTL/nonce replay protection, and fail closed in production on default/empty secrets.
- [x] **4.2 HITL Concurrency Lock & Dynamic Path Config (`REM-007` / `BUILD-PROMPT-06`):** Wrap `resume_proposal` in per-`proposal_id` `FileLock`, resolve `NEMAWASHI_STATE_DIR` / `NEMAWASHI_AUDIT_LOG_DIR` / `NEMAWASHI_CACHE_DIR` dynamically, and route resumption cleanly.
- [x] **4.3 Payload Ceilings, Singleton Engine & Ledger/Cache Quotas (`REM-008` / `BUILD-PROMPT-07`):** Add 10MB HTTP body-size middleware (HTTP 413) + `/ready` probe, singleton `NemawashiEngine`, bounded `AgentProposal` fields, cache pruning, and ledger rotation/retention.

### Phase 5: Multi-Round Orchestration, Doc/Docker Sync & Final Audit
- [x] **5.1 Multi-Round Revision & Audit Lineage (`REM-010` / `BUILD-PROMPT-08`):** Fix `ConsensusArbiterAgent.synthesize` `requires_revision` logic and preserve multi-round `votes` lineage in `AuditRecord`.
- [x] **5.2 Documentation, Prompt Registry & Docker Hardening (`REM-011` / `BUILD-PROMPT-09`):** Create `modular_prompt.md`, resolve missing prompt refs and unused `enterprise_rules.json` keys, update `Dockerfile` `HEALTHCHECK` to `/health`, and sync `README.md`, `docs/TRD.md`, and `docs/IMPLEMENTATION_PLAN.md`.
- [x] **5.3 Final Adversarial Audit & Release Sign-Off (`BUILD-PROMPT-10`):** Run full `ruff`, `mypy`, `pytest --cov=src/nemawashi --cov-fail-under=90`, and `docker compose` verification, confirming 0 open tickets in `AUDIT_REMEDIATION_LOG.md`.

---

## 3. Verification Commands Quick Reference

```powershell
# 1a. Stage 1 Quiet Verification Chain (BUILD-PROMPT-01..07: coverage reported, non-blocking)
ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/ && pytest -q --tb=short --cov=src/nemawashi --cov-report=term:skip-covered

# 1b. Stage 2 Quiet Verification Chain (BUILD-PROMPT-08..10 & CI: hard >= 90% coverage gate)
ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/ && pytest -q --tb=short --cov=src/nemawashi --cov-report=term:skip-covered --cov-fail-under=90

# 2. FastAPI Ingress Gateway (Local Non-Blocking Server)
uvicorn nemawashi.main:app --host 0.0.0.0 --port 8000

# 3. Containerized Test Suite & Gateway Build (Local & Hardened Production Override)
docker compose --profile test run --rm test
docker compose build gateway && docker compose up -d gateway
docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet
```
