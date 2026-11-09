"""Tests for State Channel Reducers, Immutability, and Consensus Amnesia Prevention (MEP-1.2)."""

import pytest
from nemawashi.core.models import AgentProposal, StructuredAgentVote
from nemawashi.core.state import (
    accumulate_costs,
    accumulate_tokens,
    append_ledger_record,
    append_vote,
    create_initial_state,
)


def test_append_vote_accumulation():
    """Verify that append_vote reducer accumulates single votes without overwrite amnesia."""
    v1 = StructuredAgentVote(stakeholder_id="security", vote="APPROVE")
    v2 = StructuredAgentVote(
        stakeholder_id="compliance", vote="MITIGATE", risk_tags=["pii"]
    )

    # 1. Starting from None
    res = append_vote(None, v1)
    assert len(res) == 1
    assert res[0].stakeholder_id == "security"

    # 2. Accumulating single vote
    res2 = append_vote(res, v2)
    assert len(res2) == 2
    assert res2[0].stakeholder_id == "security"
    assert res2[1].stakeholder_id == "compliance"

    # 3. Accumulating third single vote
    v3 = StructuredAgentVote(stakeholder_id="finops", vote="APPROVE")
    res3 = append_vote(res2, v3)
    assert len(res3) == 3
    assert [v.stakeholder_id for v in res3] == ["security", "compliance", "finops"]


def test_append_vote_rejects_list_polymorphism():
    """Verify that passing a list of votes raises TypeError at the boundary."""
    v1 = StructuredAgentVote(stakeholder_id="security", vote="APPROVE")
    v2 = StructuredAgentVote(stakeholder_id="compliance", vote="APPROVE")

    with pytest.raises(TypeError, match="Passing lists of votes is strictly forbidden"):
        append_vote(None, [v1, v2])  # type: ignore

    with pytest.raises(TypeError, match="Passing lists of votes is strictly forbidden"):
        append_vote([v1], [v2])  # type: ignore


def test_append_vote_blocks_inplace_mutations():
    """Verify that append_vote returns a deep-copied list structure blocking in-place mutations."""
    v1 = StructuredAgentVote(stakeholder_id="security", vote="APPROVE")
    v2 = StructuredAgentVote(stakeholder_id="compliance", vote="APPROVE")

    existing = [v1]
    res = append_vote(existing, v2)

    assert len(existing) == 1
    assert len(res) == 2

    # Mutating returned list does not affect original existing list
    res.append(StructuredAgentVote(stakeholder_id="sre", vote="APPROVE"))
    assert len(existing) == 1
    assert len(res) == 3


def test_append_ledger_record_accumulation():
    """Verify that append_ledger_record reducer accumulates audit blocks."""
    r1 = {"index": 0, "verdict": "APPROVE"}
    r2 = {"index": 1, "verdict": "VETO"}

    res = append_ledger_record(None, r1)
    assert len(res) == 1
    assert res[0]["index"] == 0

    res2 = append_ledger_record(res, [r2])
    assert len(res2) == 2
    assert res2[1]["index"] == 1


def test_accumulate_tokens_reducer():
    """Verify atomic token accumulation reducer."""
    assert accumulate_tokens(0, 150) == 150
    assert accumulate_tokens(150, 200) == 350
    assert accumulate_tokens(None, 50) == 50
    assert accumulate_tokens(100, None) == 100


def test_accumulate_costs_reducer():
    """Verify atomic cost accumulation reducer with precision rounding."""
    assert accumulate_costs(0.0, 0.000125) == 0.000125
    assert accumulate_costs(0.000125, 0.000250) == 0.000375
    assert accumulate_costs(None, 0.05) == 0.05


def test_create_initial_state():
    """Verify initial state construction contract including stakeholder_map and suspended_for_hitl."""
    proposal = AgentProposal(
        proposal_id="p-init",
        proposing_agent="agent-worker",
        action_type="deploy",
        action_description="deploy service",
        target_resource="k8s",
    )
    state = create_initial_state(proposal=proposal, max_rounds=5)
    assert state["proposal"] == proposal
    assert state["current_round"] == 1
    assert state["max_rounds"] == 5
    assert state["loop_veto_triggered"] is False
    assert state["votes"] == []
    assert state["stakeholder_votes"] == {}
    assert state["stakeholder_map"] == {}
    assert state["audit_ledger"] == []
    assert state["prompt_tokens"] == 0
    assert state["completion_tokens"] == 0
    assert state["total_cost_usd"] == 0.0
    assert state["suspended_for_hitl"] is False
