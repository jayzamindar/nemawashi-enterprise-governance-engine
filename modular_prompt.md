# `modular_prompt.md` — Nemawashi Governance Prompt Registry

> Centralized index of all active modular system prompts in [`prompts/`](prompts/), synchronized with [`src/nemawashi/agents/base.py`](src/nemawashi/agents/base.py) and [`PROJECT_MAP.md`](PROJECT_MAP.md).

---

## 1. Active Stakeholder System Prompts

| Persona ID | Agent Class | Prompt File | Domain & Mandate | Ingress Order | Output Contract |
|---|---|---|---|---|---|
| `PER-03` | `SecurityGuardianAgent` (`src/nemawashi/agents/security.py`) | [`prompts/security_stakeholder.md`](prompts/security_stakeholder.md) | Zero-trust architecture, wildcard ingress, IAM least-privilege, prompt injection defense | Round `N`, Step 1 | `StructuredAgentVote` (`stakeholder_id="security"`) |
| `PER-04` | `ComplianceArbiterAgent` (`src/nemawashi/agents/compliance.py`) | [`prompts/compliance_stakeholder.md`](prompts/compliance_stakeholder.md) | GDPR Art. 30, HIPAA PHI, PCI-DSS, SOC 2 Type II auditability, upstream security inspection | Round `N`, Step 2 | `StructuredAgentVote` (`stakeholder_id="compliance"`) |
| `PER-05` | `FinOpsArbiterAgent` (`src/nemawashi/agents/finops.py`) | [`prompts/finops_stakeholder.md`](prompts/finops_stakeholder.md) | Cloud spend caps, token unit economics, rightsizing, upstream mitigation cost alignment | Round `N`, Step 3 | `StructuredAgentVote` (`stakeholder_id="finops"`) |
| `PER-06` | `SRESentinelAgent` (`src/nemawashi/agents/reliability.py`) | [`prompts/sre_stakeholder.md`](prompts/sre_stakeholder.md) | Blast radius containment, canary rollouts, automated rollback probes, holistic upstream synthesis | Round `N`, Step 4 | `StructuredAgentVote` (`stakeholder_id="sre"`) |

---

## 2. Deterministic Non-Prompted Agents

The following agents execute purely deterministic logic in Python without external Markdown system prompt templates:
- **`ConsensusArbiterAgent`** ([`src/nemawashi/agents/arbiter.py`](src/nemawashi/agents/arbiter.py)): Synthesizes stakeholder `StructuredAgentVote` records, computes `composite_risk_score`, and determines `Resolution` (`UNANIMOUS_CONSENSUS`, `CONDITIONAL_ALIGNMENT`, `HUMAN_IN_THE_LOOP_ESCALATION`, or `CONSENSUS_VETO`) plus `requires_revision` routing.
- **`CostOptimizationAgent`** ([`src/nemawashi/agents/optimizer.py`](src/nemawashi/agents/optimizer.py)): Performs deterministic cloud rightsizing (spot/preemptible conversion, compute savings plans, storage tiering) via `AgentProposal.model_copy(update=...)` when FinOps issues `MITIGATE`.

---

## 3. Prompt Security & Loading Invariants

1. **Path Traversal Containment:** `BaseGovernanceAgent._load_system_prompt()` enforces `(prompts_dir / self.prompt_file).resolve().is_relative_to(prompts_dir.resolve())`, raising `ValueError` on any directory traversal attempt.
2. **Untrusted Input Isolation:** All untrusted `AgentProposal` fields (`action_description`, `target_resource`, `parameters`) are length-bounded, stripped of XML breakout tags (`</untrusted_proposal_data>`, `<instruction>`, `<system>`, `[SYSTEM]`), and wrapped in `<untrusted_proposal_data>...</untrusted_proposal_data>` blocks before Gemini invocation.
3. **Constrained Decoding:** Live Gemini calls (`GEMINI_MODEL_NAME`, `max_output_tokens=8192`) bind `StructuredAgentVote` via `clean_gemini_schema()` (`ALLOWED_GEMINI_FIELDS`, `$defs`/`$ref` dereferencing) so agents emit zero free-form conversational chatter.
4. **UTF-8 Encoding:** All prompt files are read explicitly with `encoding="utf-8"`.
