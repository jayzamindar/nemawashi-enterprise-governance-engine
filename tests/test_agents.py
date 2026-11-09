"""Tests for Specialized Stakeholder Agents and Consensus Arbiter (MEP-3.1)."""

from nemawashi.agents.arbiter import ConsensusArbiterAgent
from nemawashi.agents.compliance import ComplianceArbiterAgent
from nemawashi.agents.finops import FinOpsArbiterAgent
from nemawashi.agents.reliability import SRESentinelAgent
from nemawashi.agents.security import SecurityGuardianAgent
from nemawashi.core.models import AgentProposal, StructuredAgentVote


def test_security_guardian_evaluation():
    """Verify Security Guardian zero-trust and privilege evaluation."""
    sec = SecurityGuardianAgent()

    # Ingress 0.0.0.0/0 test
    p_ingress = AgentProposal(
        proposal_id="p-sec-1",
        proposing_agent="agent-worker",
        action_type="open_firewall",
        action_description="Allow ingress from 0.0.0.0/0 on port 22",
        target_resource="bastion-sg",
    )
    v1 = sec.evaluate(p_ingress)
    assert v1.stakeholder_id == "security"
    assert v1.vote == "MITIGATE"
    assert "unrestricted-ingress" in v1.risk_tags
    assert any("VPN" in m for m in v1.mitigation_requirements)

    # IAM role elevation test
    p_iam = AgentProposal(
        proposal_id="p-sec-2",
        proposing_agent="agent-worker",
        action_type="iam_role_elevation",
        action_description="Grant temporary admin role",
        target_resource="iam-role-admin",
    )
    v2 = sec.evaluate(p_iam)
    assert v2.vote == "MITIGATE"
    assert "iam-privilege-elevation" in v2.risk_tags


def test_compliance_arbiter_evaluation():
    """Verify Compliance Arbiter regulatory evaluation and prior vote inspection."""
    comp = ComplianceArbiterAgent()

    # Prior security network exposure triggers compliance audit mitigation
    p_sec = AgentProposal(
        proposal_id="p-comp-1",
        proposing_agent="agent-worker",
        action_type="api_gateway_deploy",
        action_description="Deploy external API gateway",
        target_resource="api-gateway",
    )
    prior_sec_vote = StructuredAgentVote(
        stakeholder_id="security",
        vote="MITIGATE",
        risk_tags=["unrestricted-ingress"],
        mitigation_requirements=["VPN only"],
    )
    v1 = comp.evaluate(p_sec, prior_votes={"security": prior_sec_vote})
    assert v1.stakeholder_id == "compliance"
    assert "compliance-audit-risk-from-network-exposure" in v1.risk_tags

    # HIPAA evaluation
    p_hipaa = AgentProposal(
        proposal_id="p-comp-2",
        proposing_agent="agent-worker",
        action_type="process_patient_records",
        action_description="Export medical patient records for analytics",
        target_resource="patient-records-bucket",
    )
    v2 = comp.evaluate(p_hipaa)
    assert v2.vote == "MITIGATE"
    assert "hipaa-protected-health-information" in v2.risk_tags


def test_finops_arbiter_evaluation():
    """Verify FinOps Arbiter spend thresholds and unit economics."""
    fin = FinOpsArbiterAgent()

    # Cost > 1000 USD
    p_expensive = AgentProposal(
        proposal_id="p-fin-1",
        proposing_agent="agent-worker",
        action_type="cluster_provision",
        action_description="Provision GPU fleet",
        target_resource="gpu-cluster",
        estimated_cost_usd=1500.0,
    )
    v1 = fin.evaluate(p_expensive)
    assert v1.stakeholder_id == "finops"
    assert v1.vote == "MITIGATE"
    assert "major-budget-consumption" in v1.risk_tags

    # Cost > 300 USD
    p_moderate = AgentProposal(
        proposal_id="p-fin-2",
        proposing_agent="agent-worker",
        action_type="nodes_add",
        action_description="Add nodes to cluster",
        target_resource="worker-pool",
        estimated_cost_usd=450.0,
    )
    v2 = fin.evaluate(p_moderate)
    assert v2.vote == "MITIGATE"
    assert "moderate-budget-allocation" in v2.risk_tags


def test_sre_sentinel_evaluation():
    """Verify SRE Sentinel blast radius and schema rollback constraints."""
    sre = SRESentinelAgent()

    # High blast radius
    p_blast = AgentProposal(
        proposal_id="p-sre-1",
        proposing_agent="agent-worker",
        action_type="restart_service",
        action_description="Restart auth service globally",
        target_resource="auth-fleet",
        estimated_blast_radius=85,
    )
    v1 = sre.evaluate(p_blast)
    assert v1.stakeholder_id == "sre"
    assert v1.vote == "MITIGATE"
    assert "high-blast-radius" in v1.risk_tags
    assert any("canary" in m.lower() for m in v1.mitigation_requirements)

    # Schema DDL migration
    p_ddl = AgentProposal(
        proposal_id="p-sre-2",
        proposing_agent="agent-worker",
        action_type="ddl_migration",
        action_description="Execute schema migration DDL on accounts table",
        target_resource="aurora-db",
        estimated_blast_radius=40,
    )
    v2 = sre.evaluate(p_ddl)
    assert v2.vote == "MITIGATE"
    assert "database-schema-mutation" in v2.risk_tags


def test_consensus_arbiter_synthesis():
    """Verify Consensus Arbiter composite risk scoring, deduplication, and verdicts."""
    arbiter = ConsensusArbiterAgent()

    proposal = AgentProposal(
        proposal_id="p-arb-1",
        proposing_agent="agent-worker",
        action_type="deploy_app",
        action_description="Deploy application service",
        target_resource="app-cluster",
        estimated_cost_usd=120.0,
        estimated_blast_radius=20,
    )

    # 1. Unanimous Consensus
    votes_approve = {
        "security": StructuredAgentVote(stakeholder_id="security", vote="APPROVE"),
        "compliance": StructuredAgentVote(stakeholder_id="compliance", vote="APPROVE"),
        "finops": StructuredAgentVote(stakeholder_id="finops", vote="APPROVE"),
        "sre": StructuredAgentVote(stakeholder_id="sre", vote="APPROVE"),
    }
    res1 = arbiter.synthesize(proposal, votes_approve)
    assert res1.verdict == "UNANIMOUS_CONSENSUS"
    assert res1.composite_risk_score < 40
    assert not res1.requires_human_approval

    # 2. Rejection triggers Consensus Veto
    votes_reject = {
        "security": StructuredAgentVote(stakeholder_id="security", vote="REJECT"),
        "compliance": StructuredAgentVote(stakeholder_id="compliance", vote="APPROVE"),
    }
    res2 = arbiter.synthesize(proposal, votes_reject)
    assert res2.verdict == "CONSENSUS_VETO"
    assert res2.composite_risk_score >= 90

    # 3. Mitigations trigger Conditional Alignment
    votes_mitigate = {
        "security": StructuredAgentVote(stakeholder_id="security", vote="MITIGATE", mitigation_requirements=["m1", "m2"]),
        "compliance": StructuredAgentVote(stakeholder_id="compliance", vote="APPROVE"),
        "finops": StructuredAgentVote(stakeholder_id="finops", vote="MITIGATE", mitigation_requirements=["m2", "m3"]),
        "sre": StructuredAgentVote(stakeholder_id="sre", vote="APPROVE"),
    }
    res3 = arbiter.synthesize(proposal, votes_mitigate)
    assert res3.verdict == "CONDITIONAL_ALIGNMENT"
    # Deduplication check: m2 should appear only once
    assert res3.mandatory_mitigations == ["m1", "m2", "m3"]
