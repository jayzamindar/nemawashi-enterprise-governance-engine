"""LangGraph State Contract for the Nemawashi Enterprise Multi-Agent Governance Engine.

Incorporates the Mitigation Loop Watchdog tracking variables (`current_round`, `max_rounds`),
reducer-driven channels (`append_vote`, `append_ledger_record`), atomic FinOps token
accounting reducers (`accumulate_tokens`, `accumulate_costs`), and `stakeholder_map` to eliminate
consensus amnesia, router lookup errors, and financial observability blind spots.
"""

import copy
from typing import Annotated, Any, Dict, List, Optional, TypedDict
from nemawashi.core.models import AgentProposal, Resolution, StructuredAgentVote


def append_vote(
    existing: Optional[List[StructuredAgentVote]],
    new_vote: StructuredAgentVote,
) -> List[StructuredAgentVote]:
    """Custom channel reducer ensuring structured votes accumulate across sequential nodes.

    Strictly accepts ONLY a single StructuredAgentVote instance (no Union/List polymorphism).
    Raises TypeError if a list or invalid type is passed at the boundary.
    Returns a deep-copied list structure to block in-place mutations.
    """
    if isinstance(new_vote, (list, tuple)):
        raise TypeError(
            f"append_vote reducer expects a single StructuredAgentVote instance, got {type(new_vote).__name__}. "
            "Passing lists of votes is strictly forbidden."
        )
    if not isinstance(new_vote, StructuredAgentVote):
        raise TypeError(
            f"append_vote reducer expects a StructuredAgentVote instance, got {type(new_vote).__name__}."
        )

    current: List[StructuredAgentVote] = copy.deepcopy(existing) if existing else []
    current.append(copy.deepcopy(new_vote))
    return current


def append_ledger_record(
    existing: Optional[List[Dict[str, Any]]],
    new_records: Any,
) -> List[Dict[str, Any]]:
    """Custom channel reducer ensuring audit records accumulate immutably."""
    current: List[Dict[str, Any]] = copy.deepcopy(existing) if existing else []
    if isinstance(new_records, list):
        current.extend(copy.deepcopy(new_records))
    else:
        current.append(copy.deepcopy(new_records))
    return current


def accumulate_tokens(existing: Optional[int], new_tokens: Optional[int]) -> int:
    """Atomic reducer accumulating prompt and completion tokens across agent turns."""
    return (existing or 0) + (new_tokens or 0)


def accumulate_costs(existing: Optional[float], new_cost: Optional[float]) -> float:
    """Atomic reducer accumulating running financial costs in USD."""
    return round((existing or 0.0) + (new_cost or 0.0), 6)


class NemawashiState(TypedDict, total=False):
    """The complete state dictionary managed across all LangGraph nodes.

    Attributes:
        proposal: The operational agent proposal undergoing governance evaluation.
        policy_passed: Whether the proposal cleared deterministic enterprise pre-checks.
        policy_violations: List of hard-rule policy violations if rejected in pre-check.
        votes: Chronologically accumulated list of StructuredAgentVote objects from sequential nodes.
            Enforces append_vote reducer to prevent consensus amnesia.
        stakeholder_votes: Mapping of stakeholder_id to StructuredAgentVote for keyed lookup.
        stakeholder_map: Clean mapping of stakeholder IDs directly to their voting decisions (e.g. {"finops": "MITIGATE"}),
            eliminating router lookup errors.
        audit_ledger: Chronologically accumulated list of audit ledger records via append_ledger_record reducer.
        prompt_tokens: Cumulative prompt/input token count accumulated across agent turns.
        completion_tokens: Cumulative completion/output token count accumulated across agent turns.
        total_cost_usd: Real-time cumulative USD cost calculated via model pricing grid.
        resolution: Synthesized consensus resolution from the Arbiter.
        current_round: Explicit deliberation iteration counter (starts at 1).
        max_rounds: Maximum allowed deliberation rounds before the loop watchdog triggers (default 3).
        loop_veto_triggered: True if the watchdog intervened to prevent infinite token drain.
        human_approved: True/False if Human-In-The-Loop gatekeeper intervened; None if pending.
        execution_permitted: Final Boolean determining if target action can proceed to execution.
        human_rationale: Operator rationale supplied during HITL gatekeeper intervention.
        audit_committed: Boolean flag ensuring the state record has been sealed in the ledger.
        audit_record_hash: SHA-256 cryptographic hash of the committed audit ledger entry.
        cost_optimization_applied: Boolean indicating if adaptive cost rightsizing was injected.
        optimized_proposal_parameters: Mutated parameters from cost optimizer if applied.
        cached_resolution: Resolution recovered from semantic cache if hit.
        cache_hit: Boolean flag indicating if proposal bypassed circle via semantic cache.
        suspended_for_hitl: Non-blocking flag indicating thread is suspended awaiting external callback.
    """

    proposal: AgentProposal
    policy_passed: bool
    policy_violations: List[str]
    votes: Annotated[List[StructuredAgentVote], append_vote]
    stakeholder_votes: Dict[str, StructuredAgentVote]
    stakeholder_map: Dict[str, str]
    audit_ledger: Annotated[List[Dict[str, Any]], append_ledger_record]
    prompt_tokens: Annotated[int, accumulate_tokens]
    completion_tokens: Annotated[int, accumulate_tokens]
    total_cost_usd: Annotated[float, accumulate_costs]
    resolution: Optional[Resolution]
    current_round: int
    max_rounds: int
    loop_veto_triggered: bool
    human_approved: Optional[bool]
    execution_permitted: bool
    human_rationale: str
    audit_committed: bool
    audit_record_hash: Optional[str]
    cost_optimization_applied: bool
    optimized_proposal_parameters: Dict[str, Any]
    cached_resolution: Optional[Resolution]
    cache_hit: bool
    suspended_for_hitl: bool


def create_initial_state(
    proposal: AgentProposal,
    max_rounds: int = 3,
    human_approved: Optional[bool] = None,
) -> NemawashiState:
    """Instantiate a pristine NemawashiState contract with initialized loop watchdog counters and reducer channels."""
    return {
        "proposal": proposal,
        "policy_passed": False,
        "policy_violations": [],
        "votes": [],
        "stakeholder_votes": {},
        "stakeholder_map": {},
        "audit_ledger": [],
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_cost_usd": 0.0,
        "resolution": None,
        "current_round": 1,
        "max_rounds": max_rounds,
        "loop_veto_triggered": False,
        "human_approved": human_approved,
        "execution_permitted": False,
        "human_rationale": "",
        "audit_committed": False,
        "audit_record_hash": None,
        "cost_optimization_applied": False,
        "optimized_proposal_parameters": {},
        "cached_resolution": None,
        "cache_hit": False,
        "suspended_for_hitl": False,
    }
