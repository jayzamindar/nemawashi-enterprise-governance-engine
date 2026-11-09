"""Tests for Adaptive Cost Optimization Agent (MEP-3.2)."""

from nemawashi.agents.optimizer import CostOptimizationAgent
from nemawashi.core.models import AgentProposal, StructuredAgentVote


def test_optimizer_high_cost_reduction():
    """Verify that proposals > $500 receive aggressive spot/savings-plan optimizations."""
    optimizer = CostOptimizationAgent()

    proposal = AgentProposal(
        proposal_id="p-opt-high",
        proposing_agent="agent-scaler",
        action_type="scale_cluster",
        action_description="Scale inference GPU cluster to 16 nodes",
        target_resource="gpu-fleet",
        estimated_cost_usd=2500.0,
        estimated_blast_radius=60,
        parameters={"nodes": 16, "instance_type": "g5.2xlarge"},
    )
    finops_vote = StructuredAgentVote(
        stakeholder_id="finops",
        vote="MITIGATE",
        risk_tags=["major-budget-consumption"],
        mitigation_requirements=["Apply spot or compute savings plan"],
    )

    optimized = optimizer.optimize(proposal, finops_vote=finops_vote)

    # Cost must be reduced by at least 40%
    assert optimized.estimated_cost_usd <= 2500.0 * 0.60
    assert optimized.parameters.get("instance_lifecycle") == "spot"
    assert optimized.parameters.get("savings_plan") == "compute_1yr_committed"
    assert "FinOps Cost-Optimized" in optimized.action_description


def test_optimizer_moderate_cost_reduction():
    """Verify that proposals between $200 and $500 receive idle shutdown and storage optimizations."""
    optimizer = CostOptimizationAgent()

    proposal = AgentProposal(
        proposal_id="p-opt-mod",
        proposing_agent="agent-dev",
        action_type="provision_env",
        action_description="Provision developer staging environment",
        target_resource="staging-vpc",
        estimated_cost_usd=400.0,
        estimated_blast_radius=30,
        parameters={"environment": "staging", "storage_type": "gp2"},
    )
    finops_vote = StructuredAgentVote(
        stakeholder_id="finops",
        vote="MITIGATE",
        risk_tags=["moderate-budget-allocation"],
        mitigation_requirements=["Attach FinOps CostCenter and Owner billing tags"],
    )

    optimized = optimizer.optimize(proposal, finops_vote=finops_vote)

    assert optimized.estimated_cost_usd < 400.0
    assert optimized.parameters.get("auto_terminate_idle_hours") == 2
    assert optimized.parameters.get("storage_tier") == "gp3_optimized"


def test_optimizer_preserves_original_proposal():
    """Verify that optimization creates an isolated copy and does not mutate the input proposal in place."""
    optimizer = CostOptimizationAgent()

    original_cost = 1200.0
    proposal = AgentProposal(
        proposal_id="p-opt-imm",
        proposing_agent="agent-worker",
        action_type="deploy",
        action_description="Deploy services",
        target_resource="k8s-nodes",
        estimated_cost_usd=original_cost,
    )

    optimized = optimizer.optimize(proposal)

    # Original proposal must remain untouched
    assert proposal.estimated_cost_usd == original_cost
    assert optimized.estimated_cost_usd < original_cost
    assert proposal.proposal_id == optimized.proposal_id
