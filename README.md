# Nemawashi: Enterprise Multi-Agent Governance Engine

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/Orchestrator-LangGraph-purple.svg)](https://github.com/langchain-ai/langgraph)
[![Pydantic v2](https://img.shields.io/badge/Data_Contracts-Pydantic_v2-red.svg)](https://docs.pydantic.dev/)
[![FastAPI](https://img.shields.io/badge/API_Gateway-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Container-Docker_Compose-2496ED.svg)](https://www.docker.com/)
[![AWS Free Tier](https://img.shields.io/badge/Cloud-AWS_EC2_Free_Tier-FF9900.svg)](https://aws.amazon.com/free/)
[![Tests](https://img.shields.io/badge/Tests-66%2F66_Passing-brightgreen.svg)](tests/)

An enterprise-grade governance engine that implements **Nemawashi** (根回し) — the authentic Japanese organizational consensus-building process — across autonomous agent swarms before any production, financial, or sensitive cloud infrastructure mutation occurs.

---

## What is Nemawashi?

In enterprise Japanese leadership, *Nemawashi* (根回し) refers to the practice of laying groundwork, building informal alignment, and establishing cross-functional consensus prior to presenting a formal proposal or executing a high-stakes initiative.

When applied to autonomous agent swarms (DevOps, SRE, FinOps, Data Bots), **Nemawashi enforces zero unilateral action**:
- No single bot can unilaterally scale expensive GPU clusters, drop databases, open firewall ports `0.0.0.0/0`, or modify IAM roles.
- Every proposal must clear a sequential circle of specialized stakeholder personas (**Security Guardian**, **Compliance Arbiter**, **FinOps Arbiter**, **SRE Sentinel**, and **Consensus Arbiter**), each accumulating upstream context and proposing concrete mitigations.
- Deliberation is strictly governed by frozen, strongly-typed contracts (`StructuredAgentVote`), completely banning conversational chatter, context dilution, and persona drift.

---

## Sequential State Machine Architecture

The engine coordinates proposals through a deterministic LangGraph `StateGraph` topology:

```mermaid
flowchart TD
    subgraph SwarmLayer["Autonomous Agent Swarm"]
        WorkerAgent["Autonomous Worker Agent\n(Submits AgentProposal)"]
    end

    subgraph StateMachine["Nemawashi Sequential StateGraph"]
        StartNode([START]) --> IntakeNode["intake_proposal_node"]
        IntakeNode --> PolicyPrecheckNode["policy_precheck_node"]
        
        %% Policy Routing
        PolicyPrecheckNode -->|policy_passed == False| ImmediateVetoNode["immediate_policy_veto_node"]
        PolicyPrecheckNode -->|policy_passed == True AND round == 1| SemanticCacheNode["semantic_cache_check_node"]
        PolicyPrecheckNode -->|policy_passed == True AND round > 1| SecurityNode["security_stakeholder_node"]

        %% Semantic Cache Pre-Check
        SemanticCacheNode -->|cache_hit == True (cosine >= 0.95)| ChainedAuditNode["commit_chained_audit_ledger_node"]
        SemanticCacheNode -->|cache_hit == False| SecurityNode
        
        %% Sequential Consensus Circle
        SecurityNode -->|append_vote| ComplianceNode["compliance_stakeholder_node"]
        ComplianceNode -->|append_vote| FinOpsNode["finops_stakeholder_node"]
        FinOpsNode -->|append_vote| SRENode["reliability_stakeholder_node"]
        SRENode -->|append_vote| ArbiterNode["arbiter_synthesis_node"]
        
        %% Consensus Router
        ArbiterNode -->|current_round > max_rounds| ImmediateVetoNode
        ArbiterNode -->|verdict == 'CONSENSUS_VETO'| ImmediateVetoNode
        ArbiterNode -->|finops == 'MITIGATE' AND round < max| CostOptNode["cost_optimization_agent_node"]
        ArbiterNode -->|verdict == 'CONDITIONAL_ALIGNMENT' AND requires_revision| RevisionNode["deliberation_revision_node"]
        ArbiterNode -->|verdict == 'HUMAN_IN_THE_LOOP_ESCALATION'| HITLNode["interactive_human_gatekeeper_node"]
        ArbiterNode -->|verdict in ('UNANIMOUS_CONSENSUS', 'CONDITIONAL_ALIGNMENT')| ChainedAuditNode
        
        %% Dynamic Optimization & Slate Reset
        CostOptNode --> RevisionNode
        RevisionNode -->|Round Increment & Slate Reset| PolicyPrecheckNode
        
        %% Non-Blocking Asynchronous Checkpoint
        HITLNode -->|State Serialization + Webhook| EndSuspended([END - Suspended Awaiting Callback])
        
        %% Terminal Ledger Enforcement
        ImmediateVetoNode --> ChainedAuditNode
        ChainedAuditNode -->|append_ledger_record + filelock| EndTerminal([END - Sealed])
    end

    subgraph IngressGateway["FastAPI Gateway (/resume)"]
        ResumeRoute["POST /resume\n(HMAC-SHA256 Signature Verification)"] -.->|Unfreezes State & Applies Sign-off| ChainedAuditNode
    end

    WorkerAgent -->|Submit Proposal| StartNode
```

---

## Security & Engineering Invariants

| Architectural Invariant | Implementation Mechanism | Enterprise Guarantee |
|---|---|---|
| **Zero Consensus Amnesia** | `typing.Annotated[List[StructuredAgentVote], append_vote]` | Monomorphic reducer strictly rejects collections with `TypeError` and deep-copies inputs; upstream votes can never be overwritten. |
| **Bounded Execution Watchdog** | `consensus_router` evaluates `current_round > max_rounds` first | Circuit breaker trips instantly when deliberation iterations exceed ceiling, halting runaway agent loops and preventing API token exhaustion. |
| **Zero Conversational Chatter** | `StructuredAgentVote(ConfigDict(extra="forbid", frozen=True))` | Eliminates free-form natural language strings between agents; all inter-agent reviews are structured, strongly typed, and deterministic. |
| **Prompt Injection Delimiting** | Enclosed within `<untrusted_proposal_data>` blocks | LLMs are instructed to treat proposal content strictly as untrusted external data, neutralizing embedded prompt overrides or jailbreaks. |
| **Cross-Platform Mutex Concurrency** | `filelock.FileLock(f"{target_path}.lock", timeout=10.0)` | Serializes concurrent ledger commits and vector cache I/O across threads/processes on POSIX and Windows, handling timeouts cleanly. |
| **Semantic Cache Vote Lineage** | `CacheEntry` stores `resolution` and `stakeholder_votes` mapping | Restores historical votes and sets `cache_hit = True` in `AuditRecord` on vector hit ($\ge 0.95$), saving 100% of LLM costs while preserving auditability. |
| **Cryptographic HITL Callback** | `POST /resume` enforces `hmac.compare_digest` on HMAC-SHA256 | Non-blocking execution suspension with state disk HMAC verification (`_state_hmac`) and path-traversal regex validation (`^[a-zA-Z0-9_-]{1,128}$`). |
| **Cloud-Native Volume Portability** | Configurable runtime paths (`NEMAWASHI_AUDIT_LOG_DIR`, etc.) | Docker containers run under unprivileged user (`UID 10001`), binding persistent state to host EBS volumes on AWS EC2 Free Tier. |
| **Zero-Cost Dual Execution** | Live Gemini 2.5 Flash with deterministic offline fallback | Runs fully live when `GEMINI_API_KEY` is present; seamlessly falls back to deterministic rule-based evaluation in CI/CD without API spend. |

---

## Multi-Model Adversarial Engineering & Verification Board

Production-grade AI governance architectures cannot rely on single-model consensus or unvalidated code generation. In high-consequence enterprise environments, blind spots in state machine transitions, concurrent file I/O, prompt handling, and cryptographic verification can lead to catastrophic infrastructure breaches.

To guarantee zero-defect reliability, every architectural contract, state transition, cryptographic boundary, and failure mode in the Nemawashi Governance Engine was subjected to **multi-model adversarial red-teaming** prior to production release. Specialized Frontier and Open-Weights models were assigned distinct adversarial roles to audit logic, probe protocol edge cases, and challenge security invariants.

All critical vulnerabilities identified during this review process have been systematically mitigated, documented in our [ADR Catalog](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/docs/adr/), and permanently guarded behind our baseline of **66 automated regression tests**.

| Model & Role | Adversarial Audit Focus | Critical Finding Caught & Hardened | Verification Artifact |
|---|---|---|---|
| **Gemini 3.8 Flash**<br>*(Lead Architect & TDD Builder)* | StateGraph topology, Pydantic v2 contracts, dual-mode `response_schema`, Docker & CI/CD orchestration. | Engineered monomorphic `append_vote` reducers (`TypeError` on collection injection), `current_round > max_rounds` circuit breaker, and non-root `python:3.12-slim` containerization. | [`GEMINI.md`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/GEMINI.md)<br>[`docs/TRD.md`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/docs/TRD.md)<br>[`Dockerfile`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/Dockerfile) |
| **DeepSeek R1**<br>*(Hostile Logic & State-Machine Auditor)* | Multi-round revision loops, state mutation leakage, and consensus race conditions. | Caught stale `stakeholder_votes` and `stakeholder_map` surviving across revision rounds; enforced round-scoped slate reset in `deliberation_revision_node` plus mandatory post-revision `policy_precheck_node` re-evaluation. | [`tests/test_langgraph_routing.py`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/tests/test_langgraph_routing.py)<br>[`ADR-001`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/docs/adr/ADR-001-deepseek-architecture-notes.md) |
| **Qwen 2.5 Coder**<br>*(Python 3.12 Concurrency & Protocol Reviewer)* | File-level mutex locking, `FileLock` deadlock/timeout edge cases, and Pydantic v2 serialization. | Hardened `ledger.py` and `cache.py` with cross-platform `FileLock`, graceful `filelock.Timeout` exception handling, and semantic cache vote-lineage preservation (`CacheEntry` with restored `stakeholder_votes`). | [`tests/test_audit_chain.py`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/tests/test_audit_chain.py)<br>[`tests/test_cache.py`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/tests/test_cache.py)<br>[`ADR-002`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/docs/adr/ADR-002-qwen-compliance-audit.md) |
| **Cohere North**<br>*(Enterprise CISO & Compliance Auditor)* | Prompt injection vectors, directory traversal, suspended state tampering, and SOC 2 / ISO 27001 auditability. | Enforced `<untrusted_proposal_data>` XML delimiters in Gemini prompts, `Path.is_relative_to()` prompt containment guards, `^[a-zA-Z0-9_-]{1,128}$` `proposal_id` regex validation, and `_state_hmac` disk integrity seals. | [`tests/test_gateway_auth.py`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/tests/test_gateway_auth.py) |
| **Llama Auto-Debugger**<br>*(Chaos & Failure-Mode QA Engineer)* | Malformed HTTP headers, signature truncation/whitespace attacks, and corrupted checkpoint recovery. | Generated adversarial test vectors for malformed `X-Nemawashi-Signature` headers (unsupported prefixes, truncated hex, whitespace), replay prevention, and corrupted suspended state recovery. | [`tests/test_gateway_auth.py`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/tests/test_gateway_auth.py)<br>[`ADR-003`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/docs/adr/ADR-003-llama-review-notes.md) |

---

## Master Documentation Hierarchy

All technical contracts, specifications, and architecture decisions adhere to our document precedence hierarchy:

```
GEMINI.md (Workspace Constitution & Source of Truth)
   │
   ├── docs/TRD.md (Technical Requirements: Schemas, State Channels, Mutex, HMAC)
   │      │
   │      └── docs/PRD.md (Product Requirements: Goals, KPIs, Scope, Compliance)
   │             │
   │             └── docs/URD.md (User Requirements: Personas, RACI, Use Cases, UAC)
   │                    │
   │                    ├── docs/IMPLEMENTATION_PLAN.md (Phased Engineering Blueprint)
   │                    │
   │                    ├── docs/DEPLOYMENT_AWS.md (AWS EC2 Free Tier Deployment Guide)
   │                    │
   │                    └── docs/adr/ (Architecture Decision Records ADR-001..006)
```

| Document | Path | Scope & Description |
|---|---|---|
| **Constitution** | [`GEMINI.md`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/GEMINI.md) | Architectural invariants, locked technology stack, and engineering protocols. |
| **TRD** | [`docs/TRD.md`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/docs/TRD.md) | Exact Pydantic v2 models, LangGraph state channels, routing matrices, and cryptographic formulas. |
| **PRD** | [`docs/PRD.md`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/docs/PRD.md) | Product vision, quantifiable SLAs/KPIs, functional epics, and NFR budgets. |
| **URD** | [`docs/URD.md`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/docs/URD.md) | 9 Actor personas, RACI governance matrix, operational use cases (UC-01 to UC-08), and User Acceptance Criteria (UAC-01 to UAC-12). |
| **Roadmap** | [`docs/IMPLEMENTATION_PLAN.md`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/docs/IMPLEMENTATION_PLAN.md) | Phased TDD engineering roadmap, vulnerability mitigation matrix, and test verification gates. |
| **AWS Guide** | [`docs/DEPLOYMENT_AWS.md`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/docs/DEPLOYMENT_AWS.md) | Step-by-step production deployment on AWS EC2 Free Tier (`t2.micro` / `t3.micro`) with Docker Compose. |
| **ADR Catalog** | [`docs/adr/`](file:///C:/WWORKING_folder/ProjectFolders/Nemawashi-Governance-Engine/docs/adr/) | Architecture Decision Records and multi-model review board syntheses (`ADR-001` through `ADR-006`). |

---

## 3-Command Quickstart

### Option 1: Local Setup via `uv` (Fastest)

```bash
# 1. Create virtual environment and install dependencies
uv venv .venv && source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt && uv pip install -e .

# 2. Run the locked test suite (66/66 automated tests passing)
pytest tests -v

# 3. Launch the interactive Rich terminal console demo
python -m nemawashi.main
```

### Option 2: Docker Compose (Production Runtime)

```bash
# 1. Configure environment file with a secure webhook secret
cp .env.example .env

# 2. Build and launch the container in detached mode
docker compose up -d --build

# 3. Verify health probe and open interactive API documentation
curl http://localhost:8000/health
# Open in browser: http://localhost:8000/docs
```

### Option 3: Containerized Test Suite Verification

```bash
# Execute complete test suite inside isolated Linux container
docker compose --profile test run --rm test
```

---

## Verification Test Matrix

The engine is backed by **66 automated unit, integration, and scenario tests** across 11 test suites with 100% pass rate:

```text
============================= test session starts ==============================
platform linux -- Python 3.12.16, pytest-9.2.0, pluggy-1.7.0
rootdir: /app, configfile: pyproject.toml
collected 66 items

tests/test_agents.py .....                                               [  7%]
tests/test_audit_chain.py ......                                         [ 16%]
tests/test_cache.py .....                                                [ 24%]
tests/test_e2e_scenarios.py .....                                        [ 31%]
tests/test_gateway_auth.py .........                                     [ 45%]
tests/test_gemini_schema.py ..                                           [ 48%]
tests/test_langgraph_routing.py ..........                               [ 63%]
tests/test_models.py .........                                           [ 77%]
tests/test_optimizer.py ...                                              [ 81%]
tests/test_policy_engine.py .....                                        [ 89%]
tests/test_state_reducers.py .......                                     [100%]

============================== 66 passed in 2.35s ==============================
```

---

## License & Governance

Licensed under the Apache License, Version 2.0. Built for enterprise autonomous agent governance under SOC 2 Type II, ISO/IEC 27001, and GDPR compliance architectures.
