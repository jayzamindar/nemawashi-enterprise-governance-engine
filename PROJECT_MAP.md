# PROJECT_MAP.md — Nemawashi Governance Engine Repository Index

> Compact architectural index (~60 lines) mapping every verified directory, module, test file, and governance document to its single-line responsibility.

## Root Governance & Configuration
- `GEMINI.md` — Nemawashi Enterprise Master Handbook (invariants, stack, coding & handover rules).
- `Enterprise_Blueprint.md` — Master production blueprint, 10 DoD tenets, and phased remediation roadmap.
- `AUDIT_REMEDIATION_LOG.md` — Sequential forensic remediation tickets (`REM-001` through `REM-011`).
- `BUILD_PROMPTS.md` — 10 ordered, self-contained build prompts (`BUILD-PROMPT-01` to `BUILD-PROMPT-10`).
- `PROJECT_MAP.md` — Repository file-to-responsibility index (this file).
- `modular_prompt.md` — Centralized prompt registry indexing all modular prompts in `prompts/`.
- `pyproject.toml` — PEP 517/621 package metadata, dependencies, and pytest configuration.
- `requirements.txt` — Core and development Python dependency list.
- `Dockerfile` & `docker-compose.yml` — Non-root (`UID 10001`) `python:3.12-slim` container & compose stack.
- `.github/workflows/ci.yml` — GitHub Actions CI pipeline (offline pytest + Docker build verify).
- `.env.example` — Template of runtime environment variables (`GEMINI_API_KEY`, `NEMAWASHI_*`).

## Source Package (`src/nemawashi/`)
- `src/nemawashi/__init__.py` — Package version and root exports.
- `src/nemawashi/main.py` — FastAPI ingress gateway (`/health`, `/resume` HMAC gate) & Rich CLI demo.
- `src/nemawashi/core/models.py` — Pydantic v2 contracts (`StructuredAgentVote`, `AgentProposal`, `Resolution`, `AuditRecord`, `UsageMetadata`, `ModelPricing`).
- `src/nemawashi/core/state.py` — `NemawashiState` TypedDict and monomorphic reducers (`append_vote`, `append_ledger_record`, `accumulate_tokens`, `accumulate_costs`).
- `src/nemawashi/core/graph.py` — LangGraph `StateGraph` topology, routing functions, and HITL state serialization.
- `src/nemawashi/core/engine.py` — `NemawashiEngine` high-level facade (`evaluate_proposal`, `resume_proposal`, `verify_audit_ledger`).
- `src/nemawashi/core/cache.py` — `SemanticProposalCache` local vector similarity cache with `FileLock` and 24h TTL.
- `src/nemawashi/agents/base.py` — `BaseGovernanceAgent` Gemini `response_schema` client + deterministic offline fallback.
- `src/nemawashi/agents/security.py` — `SecurityGuardianAgent` (zero-trust, ingress, IAM, secret exposure rules).
- `src/nemawashi/agents/compliance.py` — `ComplianceArbiterAgent` (GDPR, HIPAA, PCI-DSS, SOC 2 rules).
- `src/nemawashi/agents/finops.py` — `FinOpsArbiterAgent` (budget thresholds and cost-mitigation rules).
- `src/nemawashi/agents/reliability.py` — `SRESentinelAgent` (blast radius, canary, and rollback rules).
- `src/nemawashi/agents/arbiter.py` — `ConsensusArbiterAgent` (vote synthesis, risk scoring, HITL escalation).
- `src/nemawashi/agents/optimizer.py` — `CostOptimizationAgent` (spot/preemptible & storage rightsizing).
- `src/nemawashi/audit/ledger.py` — Terminal `commit_chained_audit_ledger_node` and `verify_ledger_chain` SHA-256 JSONL ledger.
- `src/nemawashi/policies/policy_engine.py` — Deterministic enterprise policy pre-check evaluator.
- `src/nemawashi/policies/enterprise_rules.json` — Declarative prohibited actions, targets, and cost thresholds.

## Prompts (`prompts/`)
- `prompts/security_stakeholder.md` — System prompt for Security Guardian (`PER-03`).
- `prompts/compliance_stakeholder.md` — System prompt for Compliance & Legal Arbiter (`PER-04`).
- `prompts/finops_stakeholder.md` — System prompt for FinOps Arbiter (`PER-05`).
- `prompts/sre_stakeholder.md` — System prompt for SRE Sentinel (`PER-06`).

## Test Suite (`tests/`)
- `tests/test_agents.py` — Stakeholder agent evaluation and token accounting tests.
- `tests/test_audit_chain.py` — SHA-256 chained ledger integrity and tamper detection tests.
- `tests/test_cache.py` — Semantic cache hit/miss, TTL, and rules-hash invalidation tests.
- `tests/test_e2e_scenarios.py` — End-to-end Nemawashi deliberation scenario tests.
- `tests/test_gateway_auth.py` — FastAPI `/resume` HMAC auth, path traversal, and state tamper tests.
- `tests/test_gemini_schema.py` — `StructuredAgentVote` JSON schema and offline fallback tests.
- `tests/test_langgraph_routing.py` — StateGraph conditional routing and watchdog circuit-breaker tests.
- `tests/test_models.py` — Pydantic v2 contract validation tests.
- `tests/test_optimizer.py` — `CostOptimizationAgent` rightsizing tests.
- `tests/test_policy_engine.py` — Deterministic policy pre-check tests.
- `tests/test_state_reducers.py` — `append_vote` monomorphic reducer and deep-copy tests.

## Documentation (`docs/`)
- `docs/TRD.md`, `docs/PRD.md`, `docs/URD.md`, `docs/IMPLEMENTATION_PLAN.md` — Core system specifications.
- `docs/DEPLOYMENT_AWS.md`, `docs/PRODUCTION_READINESS_REPORT.md`, `docs/Repo_Baseline_AuditReport.md`, `docs/PROMPT.md` — Deployment & audit reports.
- `docs/adr/ADR-001`..`ADR-006` — Architecture Decision Records.
