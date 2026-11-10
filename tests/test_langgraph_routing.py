"""Tests for LangGraph State Machine, Sequential Consensus Circle, and Mitigation Watchdog Routing."""

import pytest
from langgraph.graph import END

from nemawashi.core.engine import NemawashiEngine
from nemawashi.core.graph import build_nemawashi_graph, consensus_router
from nemawashi.core.models import AgentProposal, Resolution, StructuredAgentVote
from nemawashi.core.state import create_initial_state


def test_mitigation_loop_watchdog_exceeded():
    """Verify FIX HOLE 1: If current_round > max_rounds, consensus_router immediately breaks the loop to structural VETO."""
    proposal = AgentProposal(
        proposal_id="p-watchdog",
        proposing_agent="agent-worker",
        action_type="iterative_action",
        action_description="Action that triggers looping",
        target_resource="target-res",
        estimated_cost_usd=10.0,
        estimated_blast_radius=10,
    )
    resolution = Resolution(
        proposal_id="p-watchdog",
        verdict="CONDITIONAL_ALIGNMENT",
        composite_risk_score=50,
        mandatory_mitigations=["Recheck"],
        requires_human_approval=False,
        requires_revision=True,
        summary="Needs revision",
    )

    # State with current_round exceeding max_rounds
    state = create_initial_state(proposal=proposal, max_rounds=3)
    state["current_round"] = 4
    state["max_rounds"] = 3
    state["resolution"] = resolution

    route = consensus_router(state)
    assert route == "immediate_policy_veto_node", "Watchdog must break loop to immediate_policy_veto_node"


def test_mitigation_loop_watchdog_boundary_revision():
    """Verify that when current_round is at max_rounds and requires revision, it routes to veto instead of revision."""
    proposal = AgentProposal(
        proposal_id="p-watchdog-bound",
        proposing_agent="agent-worker",
        action_type="iterative_action",
        action_description="Action at loop boundary",
        target_resource="target-res",
        estimated_cost_usd=10.0,
        estimated_blast_radius=10,
    )
    resolution = Resolution(
        proposal_id="p-watchdog-bound",
        verdict="CONDITIONAL_ALIGNMENT",
        composite_risk_score=50,
        mandatory_mitigations=["Recheck"],
        requires_human_approval=False,
        requires_revision=True,
        summary="Needs revision",
    )

    state = create_initial_state(proposal=proposal, max_rounds=3)
    state["current_round"] = 3
    state["max_rounds"] = 3
    state["resolution"] = resolution

    route = consensus_router(state)
    assert route == "immediate_policy_veto_node"


def test_sequential_consensus_circle_populates_all_stakeholders(tmp_path, monkeypatch):
    """Verify that sequential execution collects structured votes from all 4 stakeholders."""
    test_ledger = tmp_path / "test_ledger.jsonl"
    test_cache = tmp_path / "test_cache.json"
    monkeypatch.setattr("nemawashi.audit.ledger.DEFAULT_LEDGER_PATH", test_ledger)
    monkeypatch.setattr("nemawashi.core.cache.DEFAULT_CACHE_PATH", test_cache)

    engine = NemawashiEngine(max_rounds=3)
    proposal = AgentProposal(
        proposal_id="p-seq",
        proposing_agent="agent-worker",
        action_type="scale_cache",
        action_description="Routine scale cache",
        target_resource="cache-pool",
        estimated_cost_usd=25.0,
        estimated_blast_radius=15,
    )

    final_state = engine.evaluate_proposal(proposal)

    votes = final_state.get("stakeholder_votes", {})
    assert "security" in votes
    assert "compliance" in votes
    assert "finops" in votes
    assert "sre" in votes

    for sid, vote in votes.items():
        assert isinstance(vote, StructuredAgentVote)
        assert vote.stakeholder_id == sid

    assert final_state.get("audit_committed") is True
    assert final_state.get("audit_record_hash") is not None
    assert final_state.get("execution_permitted") is True


def test_immediate_veto_terminal_routing(tmp_path, monkeypatch):
    """Verify that a policy violation routes straight to immediate veto and then seals in ledger."""
    test_ledger = tmp_path / "test_ledger.jsonl"
    monkeypatch.setattr("nemawashi.audit.ledger.DEFAULT_LEDGER_PATH", test_ledger)

    engine = NemawashiEngine(max_rounds=3)
    proposal = AgentProposal(
        proposal_id="p-veto",
        proposing_agent="agent-rogue",
        action_type="drop_production_database",
        action_description="Prohibited action",
        target_resource="prod-db",
        estimated_cost_usd=0.0,
        estimated_blast_radius=90,
    )

    final_state = engine.evaluate_proposal(proposal)
    assert final_state.get("policy_passed") is False
    assert final_state.get("execution_permitted") is False
    assert final_state.get("resolution").verdict == "CONSENSUS_VETO"
    assert final_state.get("audit_committed") is True


def test_hitl_approval_and_rejection_routing(tmp_path, monkeypatch):
    """Verify HITL gatekeeper routing when operator approves vs rejects."""
    test_ledger = tmp_path / "test_ledger.jsonl"
    monkeypatch.setattr("nemawashi.audit.ledger.DEFAULT_LEDGER_PATH", test_ledger)

    engine = NemawashiEngine(max_rounds=3)
    proposal = AgentProposal(
        proposal_id="p-hitl",
        proposing_agent="agent-autoscaler",
        action_type="provision_expensive_fleet",
        action_description="Provision GPU fleet",
        target_resource="gpu-fleet",
        estimated_cost_usd=1200.0,
        estimated_blast_radius=85,
    )

    # Operator approves
    state_approved = engine.evaluate_proposal(proposal, human_approved=True)
    assert state_approved.get("execution_permitted") is True
    assert state_approved.get("human_approved") is True

    # Operator rejects
    state_rejected = engine.evaluate_proposal(proposal, human_approved=False)
    assert state_rejected.get("execution_permitted") is False
    assert state_rejected.get("human_approved") is False


def test_hitl_non_blocking_suspension_and_resumption(tmp_path, monkeypatch):
    """Verify non-blocking HITL: suspends to storage, exits cleanly, and resumes via engine."""
    test_ledger = tmp_path / "test_ledger.jsonl"
    storage_dir = tmp_path / "suspended_states"
    monkeypatch.setattr("nemawashi.audit.ledger.DEFAULT_LEDGER_PATH", test_ledger)
    monkeypatch.setattr("nemawashi.core.graph.SUSPENDED_STATES_DIR", storage_dir)

    engine = NemawashiEngine(max_rounds=3)
    proposal = AgentProposal(
        proposal_id="p-async-hitl",
        proposing_agent="agent-autoscaler",
        action_type="provision_expensive_fleet",
        action_description="Provision GPU fleet",
        target_resource="gpu-fleet",
        estimated_cost_usd=1500.0,
        estimated_blast_radius=85,
    )

    # 1. Evaluate without human_approved -> must suspend cleanly without blocking
    suspended_state = engine.evaluate_proposal(proposal)
    assert suspended_state.get("suspended_for_hitl") is True
    assert suspended_state.get("execution_permitted") is False
    assert suspended_state.get("audit_committed") is False

    # Check file exists in local storage
    state_file = storage_dir / f"{proposal.proposal_id}.json"
    assert state_file.exists(), f"State file should exist at {state_file}"

    # 2. Resume execution with operator decision
    resumed_state = engine.resume_proposal(
        proposal_id=proposal.proposal_id,
        approved=True,
        rationale="Executive sign-off via testing harness",
        storage_dir=storage_dir,
    )
    assert resumed_state.get("suspended_for_hitl") is False
    assert resumed_state.get("human_approved") is True
    assert resumed_state.get("execution_permitted") is True
    assert resumed_state.get("audit_committed") is True
    assert resumed_state.get("audit_record_hash") is not None


def test_fastapi_gateway_resume_endpoint(tmp_path, monkeypatch):
    """Verify FastAPI gateway /resume POST endpoint resumes suspended deliberations."""
    from fastapi import HTTPException
    from nemawashi.main import ResumeProposalRequest, resume_deliberation

    test_ledger = tmp_path / "test_ledger.jsonl"
    storage_dir = tmp_path / "suspended_states"
    monkeypatch.setattr("nemawashi.audit.ledger.DEFAULT_LEDGER_PATH", test_ledger)
    monkeypatch.setattr("nemawashi.core.graph.SUSPENDED_STATES_DIR", storage_dir)

    engine = NemawashiEngine(max_rounds=3)
    proposal = AgentProposal(
        proposal_id="p-gateway-hitl",
        proposing_agent="agent-autoscaler",
        action_type="provision_gpu_cluster",
        action_description="Provision large GPU inference nodes",
        target_resource="gpu-fleet",
        estimated_cost_usd=2000.0,
        estimated_blast_radius=90,
    )

    # Stage 1: Suspend proposal
    suspended_state = engine.evaluate_proposal(proposal)
    assert suspended_state.get("suspended_for_hitl") is True

    # Test 404 for nonexistent proposal
    with pytest.raises(HTTPException) as exc_info:
        resume_deliberation(ResumeProposalRequest(proposal_id="nonexistent-id", approved=True))
    assert exc_info.value.status_code == 404

    # Test 200 for valid proposal
    response = resume_deliberation(
        ResumeProposalRequest(
            proposal_id=proposal.proposal_id,
            approved=True,
            rationale="VP Approved via FastAPI gateway",
        )
    )
    assert response.status == "RESUMED"
    assert response.proposal_id == proposal.proposal_id
    assert response.execution_permitted is True
    assert response.human_approved is True
    assert response.audit_committed is True
    assert response.audit_record_hash is not None


def test_stakeholder_map_population(tmp_path, monkeypatch):
    """Verify that stakeholder_map is populated by all stakeholders and matches decisions."""
    test_ledger = tmp_path / "test_ledger.jsonl"
    test_cache = tmp_path / "test_cache.json"
    monkeypatch.setattr("nemawashi.audit.ledger.DEFAULT_LEDGER_PATH", test_ledger)
    monkeypatch.setattr("nemawashi.core.cache.DEFAULT_CACHE_PATH", test_cache)

    engine = NemawashiEngine(max_rounds=3)
    proposal = AgentProposal(
        proposal_id="p-map-test",
        proposing_agent="agent-worker",
        action_type="scale_cache",
        action_description="Routine scale cache",
        target_resource="cache-pool",
        estimated_cost_usd=25.0,
        estimated_blast_radius=15,
    )

    final_state = engine.evaluate_proposal(proposal)
    s_map = final_state.get("stakeholder_map", {})
    assert "security" in s_map
    assert "compliance" in s_map
    assert "finops" in s_map
    assert "sre" in s_map

    votes = final_state.get("stakeholder_votes", {})
    for sid, vote_str in s_map.items():
        assert vote_str == votes[sid].vote
