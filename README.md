# Nemawashi: Enterprise Multi-Agent Governance Engine

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/Orchestrator-LangGraph-purple.svg)](https://github.com/langchain-ai/langgraph)
[![Pydantic v2](https://img.shields.io/badge/Data_Contracts-Pydantic_v2-red.svg)](https://docs.pydantic.dev/)
[![Gemini Native](https://img.shields.io/badge/LLM-Gemini_Structured_Outputs-orange.svg)](https://ai.google.dev/)

An enterprise-grade governance engine that implements **Nemawashi** (根回し) — the authentic Japanese organizational consensus-building process — across autonomous agent swarms before any production or sensitive action takes place.

---

## Key Architectural Principles & Hard Fixes

1. **Sequential Nemawashi Deliberation**:
   Stakeholders do not evaluate actions in disconnected silos. Instead, review proceeds through an ordered circle:
   $$\text{Security Guardian} \longrightarrow \text{Compliance Arbiter} \longrightarrow \text{FinOps Arbiter} \longrightarrow \text{SRE Sentinel} \longrightarrow \text{Consensus Arbiter}$$
2. **Mitigation Loop Watchdog**:
   Guards against runaway deliberation cycles and infinite API token drain by bounding loops to `max_rounds: int = 3`. If `current_round > max_rounds`, the engine triggers a deterministic structural `CONSENSUS_VETO`.
3. **Structured Memory Contract (`StructuredAgentVote`)**:
   Eliminates context dilution, persona drift, and token bloat. Agents communicate solely through strongly-typed Pydantic v2 votes (`stakeholder_id`, `vote`, `risk_tags`, `mitigation_requirements`) bound to Gemini's native `response_schema`.
4. **Cryptographically Chained SHA-256 Terminal Ledger**:
   `commit_chained_audit_ledger_node` acts as a strict terminal node in the LangGraph topology directly preceding `END`. State cannot be mutated once sealed, and every block chains the SHA-256 hash of its predecessor.

---

## Directory Manifest

```
Nemawashi-Governance-Engine/
├── .vscode/               # VS Code workspace settings, launch configs, extensions
├── prompts/               # Stakeholder persona prompts & master directive
├── src/nemawashi/
│   ├── core/              # Models, State contract, LangGraph topology, Engine facade
│   ├── agents/            # Security, Compliance, FinOps, SRE, and Arbiter agents
│   ├── policies/          # Fast deterministic hard-rule pre-checks
│   └── audit/             # Cryptographically chained SHA-256 ledger
├── tests/                 # Comprehensive test suite covering models, policies, routing, audit
├── pyproject.toml         # Standard Python packaging configuration
└── requirements.txt       # Pinned production dependencies
```

---

## Quickstart

### 1. Provision Virtual Environment
```powershell
uv venv --python 3.12 .venv
.\activate.ps1
uv pip install -r requirements.txt
```

### 2. Run Test Suite
```powershell
python -m pytest tests -v
```

### 3. Run Live Interactive CLI Demo
```powershell
python -m nemawashi.main
```
