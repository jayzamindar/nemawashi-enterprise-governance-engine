"""LangGraph Sequential StateGraph Topology.

Implements the sequential Nemawashi consensus circle, the Mitigation Loop Watchdog,
semantic vector caching, dynamic cost optimization branching, non-blocking asynchronous
human-in-the-loop escalation with local storage persistence, and the strict terminal
immutable audit ledger node.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, Literal, Optional
from langgraph.graph import END, START, StateGraph
from rich.console import Console
from rich.panel import Panel

from nemawashi.agents.arbiter import ConsensusArbiterAgent
from nemawashi.agents.compliance import ComplianceArbiterAgent
from nemawashi.agents.finops import FinOpsArbiterAgent
from nemawashi.agents.optimizer import CostOptimizationAgent
from nemawashi.agents.reliability import SRESentinelAgent
from nemawashi.agents.security import SecurityGuardianAgent
from nemawashi.audit.ledger import commit_chained_audit_ledger_node
from nemawashi.core.cache import SemanticProposalCache
from nemawashi.core.models import AgentProposal, Resolution, StructuredAgentVote
from nemawashi.core.state import NemawashiState
from nemawashi.policies.policy_engine import evaluate_proposal_policies

console = Console()
SUSPENDED_STATES_DIR = Path("storage") / "suspended_states"


def serialize_state(state: NemawashiState) -> Dict[str, Any]:
    """Serialize NemawashiState into a JSON-compatible dictionary."""
    data: Dict[str, Any] = {}
    for k, v in state.items():
        if k == "proposal" and isinstance(v, AgentProposal):
            data[k] = v.model_dump()
        elif k == "resolution" and isinstance(v, Resolution):
            data[k] = v.model_dump()
        elif k == "cached_resolution" and isinstance(v, Resolution):
            data[k] = v.model_dump()
        elif k == "votes" and isinstance(v, list):
            data[k] = [
                item.model_dump() if isinstance(item, StructuredAgentVote) else item
                for item in v
            ]
        elif k == "stakeholder_votes" and isinstance(v, dict):
            data[k] = {
                sk: sv.model_dump() if isinstance(sv, StructuredAgentVote) else sv
                for sk, sv in v.items()
            }
        else:
            data[k] = v
    return data


def deserialize_state(data: Dict[str, Any]) -> NemawashiState:
    """Deserialize a dictionary back into a fully typed NemawashiState contract."""
    state = dict(data)
    if "proposal" in state and isinstance(state["proposal"], dict):
        state["proposal"] = AgentProposal.model_validate(state["proposal"])
    if "resolution" in state and isinstance(state["resolution"], dict):
        state["resolution"] = Resolution.model_validate(state["resolution"])
    if "cached_resolution" in state and isinstance(state["cached_resolution"], dict):
        state["cached_resolution"] = Resolution.model_validate(
            state["cached_resolution"]
        )
    if "votes" in state and isinstance(state["votes"], list):
        state["votes"] = [
            StructuredAgentVote.model_validate(v) if isinstance(v, dict) else v
            for v in state["votes"]
        ]
    if "stakeholder_votes" in state and isinstance(state["stakeholder_votes"], dict):
        state["stakeholder_votes"] = {
            k: StructuredAgentVote.model_validate(v) if isinstance(v, dict) else v
            for k, v in state["stakeholder_votes"].items()
        }
    if "stakeholder_map" not in state or not isinstance(state["stakeholder_map"], dict):
        state["stakeholder_map"] = {
            k: v.vote if isinstance(v, StructuredAgentVote) else v.get("vote", "")
            for k, v in state.get("stakeholder_votes", {}).items()
        }
    return state  # type: ignore


def save_suspended_state(
    state: NemawashiState, storage_dir: Optional[Path] = None
) -> Path:
    """Persist suspended NemawashiState to local storage for non-blocking asynchronous resumption."""
    target_dir = storage_dir or SUSPENDED_STATES_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    proposal_id = state["proposal"].proposal_id
    file_path = target_dir / f"{proposal_id}.json"
    serialized = serialize_state(state)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(serialized, f, indent=2)
    return file_path


def load_suspended_state(
    proposal_id: str, storage_dir: Optional[Path] = None
) -> NemawashiState:
    """Load and deserialize a suspended NemawashiState from local storage."""
    target_dir = storage_dir or SUSPENDED_STATES_DIR
    file_path = target_dir / f"{proposal_id}.json"
    if not file_path.exists():
        raise FileNotFoundError(
            f"Suspended state file not found for proposal '{proposal_id}' at {file_path}"
        )
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return deserialize_state(data)


def emit_mock_notification_webhook(state: NemawashiState) -> Dict[str, Any]:
    """Emit an asynchronous webhook notification payload and log out-of-band escalation."""
    proposal = state["proposal"]
    resolution = state.get("resolution")
    payload = {
        "event": "HUMAN_IN_THE_LOOP_ESCALATION",
        "proposal_id": proposal.proposal_id,
        "action_type": proposal.action_type,
        "action_description": proposal.action_description,
        "target_resource": proposal.target_resource,
        "estimated_cost_usd": proposal.estimated_cost_usd,
        "estimated_blast_radius": proposal.estimated_blast_radius,
        "composite_risk_score": resolution.composite_risk_score if resolution else 85,
        "finops_metrics": {
            "current_round": state.get("current_round", 1),
            "prompt_tokens": state.get("prompt_tokens", 0),
            "completion_tokens": state.get("completion_tokens", 0),
            "total_cost_usd": state.get("total_cost_usd", 0.0),
        },
        "callback_endpoint": "/resume",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    console.print(
        Panel(
            f"[bold red]ASYNCHRONOUS ESCALATION DISPATCHED[/bold red]\n\n"
            f"[bold cyan]Proposal ID:[/bold cyan] {proposal.proposal_id}\n"
            f"[bold cyan]Action:[/bold cyan] {proposal.action_type}\n"
            f"[bold cyan]Cost:[/bold cyan] ${proposal.estimated_cost_usd:.2f} USD\n"
            f"[bold cyan]Blast Radius:[/bold cyan] {proposal.estimated_blast_radius}/100\n"
            f"[bold yellow]=== FINOPS ACCRUED METRICS ===[/bold yellow]\n"
            f"Prompt Tokens: {state.get('prompt_tokens', 0)}\n"
            f"Completion Tokens: {state.get('completion_tokens', 0)}\n"
            f"Total Cost USD: ${state.get('total_cost_usd', 0.0):.4f}\n\n"
            f"[bold green]Ingress Resumption Endpoint:[/bold green] POST /resume\n"
            f"[dim]Thread suspended cleanly without console block. State saved to storage.[/dim]",
            title="Non-Blocking HITL Webhook Alert",
            border_style="yellow",
        )
    )
    return payload


def intake_proposal_node(state: NemawashiState) -> Dict[str, Any]:
    """Ingests and validates the initial AgentProposal in state."""
    proposal = state["proposal"]
    current_round = state.get("current_round", 1)
    max_rounds = state.get("max_rounds", 3)
    return {
        "current_round": current_round,
        "max_rounds": max_rounds,
        "stakeholder_votes": dict(state.get("stakeholder_votes", {})),
        "stakeholder_map": dict(state.get("stakeholder_map", {})),
    }


def policy_precheck_node(state: NemawashiState) -> Dict[str, Any]:
    """Evaluates the proposal against deterministic enterprise policies."""
    proposal = state["proposal"]
    result = evaluate_proposal_policies(proposal)
    return {
        "policy_passed": result.passed,
        "policy_violations": result.violations,
    }


def policy_routing(
    state: NemawashiState,
) -> Literal["semantic_cache_check_node", "immediate_policy_veto_node"]:
    """Routes based on deterministic policy evaluation."""
    if state.get("policy_passed", False):
        return "semantic_cache_check_node"
    return "immediate_policy_veto_node"


def semantic_cache_check_node(state: NemawashiState) -> Dict[str, Any]:
    """Pre-Circle Semantic Cache Guardrail Layer.

    Queries local vector cache for semantically equivalent proposals (cosine >= 0.95).
    Upon a cache hit, bypasses the multi-agent circle to eliminate duplicate token costs and latency.
    """
    cache = SemanticProposalCache()
    match = cache.lookup(state["proposal"])

    if match and match.similarity >= 0.95:
        res = match.resolution
        permitted = res.verdict in ("UNANIMOUS_CONSENSUS", "CONDITIONAL_ALIGNMENT")
        return {
            "cache_hit": True,
            "cached_resolution": res,
            "resolution": res,
            "execution_permitted": permitted,
        }

    return {"cache_hit": False}


def cache_routing(
    state: NemawashiState,
) -> Literal["commit_chained_audit_ledger_node", "security_stakeholder_node"]:
    """Bypasses consensus circle if proposal resolution was found in semantic cache."""
    if state.get("cache_hit", False):
        return "commit_chained_audit_ledger_node"
    return "security_stakeholder_node"


def security_stakeholder_node(state: NemawashiState) -> Dict[str, Any]:
    """First sequential stakeholder: Security Guardian."""
    agent = SecurityGuardianAgent()
    vote, tokens = agent.evaluate_with_usage(
        proposal=state["proposal"],
        prior_votes=state.get("stakeholder_votes", {}),
    )
    votes = dict(state.get("stakeholder_votes", {}))
    votes["security"] = vote
    stakeholder_map = dict(state.get("stakeholder_map", {}))
    stakeholder_map["security"] = vote.vote

    return {
        "votes": vote,
        "stakeholder_votes": votes,
        "stakeholder_map": stakeholder_map,
        "prompt_tokens": tokens.prompt_tokens,
        "completion_tokens": tokens.completion_tokens,
        "total_cost_usd": tokens.cost_usd,
    }


def compliance_stakeholder_node(state: NemawashiState) -> Dict[str, Any]:
    """Second sequential stakeholder: Compliance & Legal Arbiter."""
    agent = ComplianceArbiterAgent()
    vote, tokens = agent.evaluate_with_usage(
        proposal=state["proposal"],
        prior_votes=state.get("stakeholder_votes", {}),
    )
    votes = dict(state.get("stakeholder_votes", {}))
    votes["compliance"] = vote
    stakeholder_map = dict(state.get("stakeholder_map", {}))
    stakeholder_map["compliance"] = vote.vote

    return {
        "votes": vote,
        "stakeholder_votes": votes,
        "stakeholder_map": stakeholder_map,
        "prompt_tokens": tokens.prompt_tokens,
        "completion_tokens": tokens.completion_tokens,
        "total_cost_usd": tokens.cost_usd,
    }


def finops_stakeholder_node(state: NemawashiState) -> Dict[str, Any]:
    """Third sequential stakeholder: FinOps Arbiter."""
    agent = FinOpsArbiterAgent()
    vote, tokens = agent.evaluate_with_usage(
        proposal=state["proposal"],
        prior_votes=state.get("stakeholder_votes", {}),
    )
    votes = dict(state.get("stakeholder_votes", {}))
    votes["finops"] = vote
    stakeholder_map = dict(state.get("stakeholder_map", {}))
    stakeholder_map["finops"] = vote.vote

    return {
        "votes": vote,
        "stakeholder_votes": votes,
        "stakeholder_map": stakeholder_map,
        "prompt_tokens": tokens.prompt_tokens,
        "completion_tokens": tokens.completion_tokens,
        "total_cost_usd": tokens.cost_usd,
    }


def reliability_stakeholder_node(state: NemawashiState) -> Dict[str, Any]:
    """Fourth sequential stakeholder: SRE Sentinel."""
    agent = SRESentinelAgent()
    vote, tokens = agent.evaluate_with_usage(
        proposal=state["proposal"],
        prior_votes=state.get("stakeholder_votes", {}),
    )
    votes = dict(state.get("stakeholder_votes", {}))
    votes["sre"] = vote
    stakeholder_map = dict(state.get("stakeholder_map", {}))
    stakeholder_map["sre"] = vote.vote

    return {
        "votes": vote,
        "stakeholder_votes": votes,
        "stakeholder_map": stakeholder_map,
        "prompt_tokens": tokens.prompt_tokens,
        "completion_tokens": tokens.completion_tokens,
        "total_cost_usd": tokens.cost_usd,
    }


def arbiter_synthesis_node(state: NemawashiState) -> Dict[str, Any]:
    """Consensus Arbiter synthesizes all structured votes into a Resolution."""
    agent = ConsensusArbiterAgent()
    resolution = agent.synthesize(
        proposal=state["proposal"],
        votes=state.get("stakeholder_votes", {}),
        current_round=state.get("current_round", 1),
        max_rounds=state.get("max_rounds", 3),
        requires_revision=state.get("resolution").requires_revision
        if state.get("resolution")
        else False,
    )
    return {"resolution": resolution}


def cost_optimization_agent_node(state: NemawashiState) -> Dict[str, Any]:
    """Adaptive Cost Optimization Persona.

    Intercepts proposals flagged for budget mitigations and restructures the infrastructure
    payload with spot instances, compute savings plans, or rightsized storage tiers.
    """
    optimizer = CostOptimizationAgent()
    finops_vote = state.get("stakeholder_votes", {}).get("finops")
    optimized_proposal = optimizer.optimize(
        proposal=state["proposal"],
        finops_vote=finops_vote,
    )

    return {
        "proposal": optimized_proposal,
        "cost_optimization_applied": True,
        "optimized_proposal_parameters": optimized_proposal.parameters,
    }


def consensus_router(
    state: NemawashiState,
) -> Literal[
    "immediate_policy_veto_node",
    "cost_optimization_agent_node",
    "deliberation_revision_node",
    "interactive_human_gatekeeper_node",
    "commit_chained_audit_ledger_node",
]:
    """Conditional router enforcing the Mitigation Loop Watchdog and verdict dispatch.

    - Watchdog: If current_round > max_rounds, immediately breaks the iteration loop
      and routes straight to structural VETO, preventing infinite API token drain.
    - Stakeholder Map: Direct lookup via stakeholder_map eliminates router lookup errors.
    - Non-blocking HITL: If escalation triggers and human_approved is None, serializes
      state context to local storage, emits mock webhook alert, and exits cleanly.
    """
    current_round = state.get("current_round", 1)
    max_rounds = state.get("max_rounds", 3)

    # 1. Watchdog condition: round exceeds allowed ceiling
    if current_round > max_rounds:
        return "immediate_policy_veto_node"

    resolution = state.get("resolution")
    if not resolution:
        return "immediate_policy_veto_node"

    verdict = resolution.verdict

    if verdict == "CONSENSUS_VETO":
        return "immediate_policy_veto_node"

    # 2. Adaptive Cost Optimization Branching via stakeholder_map
    finops_decision = state.get("stakeholder_map", {}).get("finops")
    finops_vote = state.get("stakeholder_votes", {}).get("finops")
    if (
        finops_decision == "MITIGATE"
        and finops_vote
        and any("budget" in tag or "cost" in tag for tag in finops_vote.risk_tags)
        and not state.get("cost_optimization_applied", False)
        and current_round < max_rounds
    ):
        return "cost_optimization_agent_node"

    # 3. Revision Loop
    if verdict == "CONDITIONAL_ALIGNMENT" and resolution.requires_revision:
        if current_round >= max_rounds:
            return "immediate_policy_veto_node"
        return "deliberation_revision_node"

    # 4. Human-in-the-Loop Escalation (Non-blocking asynchronous serialization)
    if verdict == "HUMAN_IN_THE_LOOP_ESCALATION":
        if state.get("human_approved") is None:
            save_suspended_state(state)
            emit_mock_notification_webhook(state)
        return "interactive_human_gatekeeper_node"

    return "commit_chained_audit_ledger_node"


def deliberation_revision_node(state: NemawashiState) -> Dict[str, Any]:
    """Advances deliberation round counter and prepares state for next review cycle."""
    current_round = state.get("current_round", 1)
    return {
        "current_round": current_round + 1,
    }


def immediate_policy_veto_node(state: NemawashiState) -> Dict[str, Any]:
    """Structural VETO node for policy breaches, rejections, or loop watchdog interventions."""
    current_round = state.get("current_round", 1)
    max_rounds = state.get("max_rounds", 3)
    loop_veto = (current_round > max_rounds) or (
        state.get("resolution") is not None
        and state["resolution"].requires_revision
        and current_round >= max_rounds
    )

    violations = list(state.get("policy_violations", []))

    if loop_veto:
        watchdog_msg = (
            f"WATCHDOG_INTERVENTION: Deliberation round {current_round} exceeded max_rounds ({max_rounds}). "
            "Structural VETO triggered to prevent infinite token drain."
        )
        violations.append(watchdog_msg)
        resolution = Resolution(
            proposal_id=state["proposal"].proposal_id,
            verdict="CONSENSUS_VETO",
            composite_risk_score=100,
            mandatory_mitigations=[
                "WATCHDOG_INTERVENTION: Loop terminated by platform watchdog"
            ],
            requires_human_approval=False,
            requires_revision=False,
            summary="Structural VETO: Deliberation round limit exceeded.",
        )
        return {
            "policy_passed": False,
            "policy_violations": violations,
            "resolution": resolution,
            "loop_veto_triggered": True,
            "execution_permitted": False,
        }

    # Standard policy breach or arbiter veto
    if not violations:
        violations.append("Consensus VETO issued during multi-agent deliberation.")

    resolution = state.get("resolution") or Resolution(
        proposal_id=state["proposal"].proposal_id,
        verdict="CONSENSUS_VETO",
        composite_risk_score=100,
        mandatory_mitigations=[f"VIOLATION: {v}" for v in violations],
        requires_human_approval=False,
        requires_revision=False,
        summary="Structural VETO: Policy violation or security threshold breach.",
    )
    return {
        "policy_passed": False,
        "policy_violations": violations,
        "resolution": resolution,
        "execution_permitted": False,
    }


def interactive_human_gatekeeper_node(state: NemawashiState) -> Dict[str, Any]:
    """Non-blocking human gatekeeper node.

    Synchronous input() is completely removed to eliminate blocking execution loops.
    If human_approved is None, marks state as suspended so the execution thread exits cleanly.
    When human_approved is set (via FastAPI /resume gateway or test override), applies
    the decision and transitions toward the terminal ledger node.
    """
    if state.get("human_approved") is None:
        return {
            "suspended_for_hitl": True,
            "execution_permitted": False,
        }

    approved = bool(state.get("human_approved"))
    return {
        "human_approved": approved,
        "execution_permitted": approved,
        "human_rationale": state.get(
            "human_rationale", "Operator decision supplied via gateway callback"
        ),
        "suspended_for_hitl": False,
    }


def hitl_gatekeeper_routing(
    state: NemawashiState,
) -> Literal["commit_chained_audit_ledger_node", END]:  # type: ignore
    """Routes to END if thread is suspended waiting for callback, or to ledger if decision is finalized."""
    if state.get("suspended_for_hitl", False):
        return END
    return "commit_chained_audit_ledger_node"


def build_nemawashi_graph() -> StateGraph:
    """Constructs the compiled Nemawashi LangGraph StateGraph.

    Enforces:
    1. Pre-circle semantic vector caching
    2. Sequential consensus circle passing StructuredAgentVote
    3. Deterministic loop watchdog routing
    4. Adaptive cost optimizer branching
    5. Non-blocking asynchronous HITL suspension and resumption
    6. Strict terminal immutable audit ledger node preceding END
    """
    builder = StateGraph(NemawashiState)

    # Register Nodes
    builder.add_node("intake_proposal_node", intake_proposal_node)
    builder.add_node("policy_precheck_node", policy_precheck_node)
    builder.add_node("semantic_cache_check_node", semantic_cache_check_node)
    builder.add_node("security_stakeholder_node", security_stakeholder_node)
    builder.add_node("compliance_stakeholder_node", compliance_stakeholder_node)
    builder.add_node("finops_stakeholder_node", finops_stakeholder_node)
    builder.add_node("reliability_stakeholder_node", reliability_stakeholder_node)
    builder.add_node("arbiter_synthesis_node", arbiter_synthesis_node)
    builder.add_node("cost_optimization_agent_node", cost_optimization_agent_node)
    builder.add_node("deliberation_revision_node", deliberation_revision_node)
    builder.add_node("immediate_policy_veto_node", immediate_policy_veto_node)
    builder.add_node(
        "interactive_human_gatekeeper_node", interactive_human_gatekeeper_node
    )

    # Terminal Ledger Node Preceding END
    builder.add_node(
        "commit_chained_audit_ledger_node", commit_chained_audit_ledger_node
    )

    # Add Transitions
    builder.add_edge(START, "intake_proposal_node")
    builder.add_edge("intake_proposal_node", "policy_precheck_node")

    # Policy Routing: Policy Pass -> Semantic Cache Check, Policy Fail -> Immediate Veto
    builder.add_conditional_edges(
        "policy_precheck_node",
        policy_routing,
        {
            "semantic_cache_check_node": "semantic_cache_check_node",
            "immediate_policy_veto_node": "immediate_policy_veto_node",
        },
    )

    # Semantic Cache Routing: Hit -> Terminal Ledger, Miss -> Security Node
    builder.add_conditional_edges(
        "semantic_cache_check_node",
        cache_routing,
        {
            "commit_chained_audit_ledger_node": "commit_chained_audit_ledger_node",
            "security_stakeholder_node": "security_stakeholder_node",
        },
    )

    # Sequential Nemawashi Circle
    builder.add_edge("security_stakeholder_node", "compliance_stakeholder_node")
    builder.add_edge("compliance_stakeholder_node", "finops_stakeholder_node")
    builder.add_edge("finops_stakeholder_node", "reliability_stakeholder_node")
    builder.add_edge("reliability_stakeholder_node", "arbiter_synthesis_node")

    # Consensus Router (Watchdog, Cost Optimization, Revision & Verdict Dispatch)
    builder.add_conditional_edges(
        "arbiter_synthesis_node",
        consensus_router,
        {
            "immediate_policy_veto_node": "immediate_policy_veto_node",
            "cost_optimization_agent_node": "cost_optimization_agent_node",
            "deliberation_revision_node": "deliberation_revision_node",
            "interactive_human_gatekeeper_node": "interactive_human_gatekeeper_node",
            "commit_chained_audit_ledger_node": "commit_chained_audit_ledger_node",
        },
    )

    # Cost Optimizer feeds into deliberation revision
    builder.add_edge("cost_optimization_agent_node", "deliberation_revision_node")

    # Deliberation Loop: revision node feeds back to security
    builder.add_edge("deliberation_revision_node", "security_stakeholder_node")

    # Terminal Funnels
    builder.add_edge("immediate_policy_veto_node", "commit_chained_audit_ledger_node")

    # Gatekeeper conditional routing: Suspended -> END, Decided -> Ledger Node
    builder.add_conditional_edges(
        "interactive_human_gatekeeper_node",
        hitl_gatekeeper_routing,
        {
            "commit_chained_audit_ledger_node": "commit_chained_audit_ledger_node",
            END: END,
        },
    )

    # Strict Terminal Node Preceding END
    builder.add_edge("commit_chained_audit_ledger_node", END)

    return builder
