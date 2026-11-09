"""Tests for Deterministic Policy Pre-check Engine."""

from nemawashi.core.models import AgentProposal
from nemawashi.policies.policy_engine import evaluate_proposal_policies


def test_clean_proposal_passes_precheck():
    """Verify that a compliant, low-impact proposal passes policy pre-check."""
    proposal = AgentProposal(
        proposal_id="p-clean",
        proposing_agent="agent-infra",
        action_type="scale_cache",
        action_description="Scale redis cache replicas",
        target_resource="cache-redis-01",
        estimated_cost_usd=20.0,
        estimated_blast_radius=10,
    )
    result = evaluate_proposal_policies(proposal)
    assert result.passed is True
    assert len(result.violations) == 0
    assert result.requires_hitl is False


def test_prohibited_action_triggers_hard_veto():
    """Verify that blacklisted operations trigger immediate hard policy violations."""
    proposal = AgentProposal(
        proposal_id="p-drop",
        proposing_agent="agent-rogue",
        action_type="drop_production_database",
        action_description="Drop tables in database",
        target_resource="db-cluster",
        estimated_cost_usd=0.0,
        estimated_blast_radius=90,
    )
    result = evaluate_proposal_policies(proposal)
    assert result.passed is False
    assert any("PROHIBITED_ACTION" in v for v in result.violations)


def test_protected_target_substring_triggers_veto():
    """Verify that targeting protected resource substrings triggers immediate veto."""
    proposal = AgentProposal(
        proposal_id="p-protected",
        proposing_agent="agent-worker",
        action_type="restart_node",
        action_description="Restart node",
        target_resource="prod-primary-db-instance-0",
        estimated_cost_usd=0.0,
        estimated_blast_radius=50,
    )
    result = evaluate_proposal_policies(proposal)
    assert result.passed is False
    assert any("PROTECTED_RESOURCE" in v for v in result.violations)


def test_excessive_cost_triggers_hard_veto():
    """Verify that costs exceeding the absolute platform ceiling trigger a veto."""
    proposal = AgentProposal(
        proposal_id="p-costly",
        proposing_agent="agent-worker",
        action_type="provision_nodes",
        action_description="Provision massive fleet",
        target_resource="worker-cluster",
        estimated_cost_usd=10000.0,
        estimated_blast_radius=60,
    )
    result = evaluate_proposal_policies(proposal)
    assert result.passed is False
    assert any("BUDGET_CEILING_BREACH" in v for v in result.violations)


def test_hitl_escalation_triggers():
    """Verify that financial or blast radius thresholds trigger HITL escalation."""
    proposal = AgentProposal(
        proposal_id="p-hitl",
        proposing_agent="agent-worker",
        action_type="provision_gpus",
        action_description="Provision GPU nodes",
        target_resource="ml-cluster",
        estimated_cost_usd=750.0,
        estimated_blast_radius=85,
    )
    result = evaluate_proposal_policies(proposal)
    assert result.passed is True
    assert result.requires_hitl is True
    assert len(result.hitl_reasons) >= 2
