"""Tests for Nemawashi Pydantic Core Models and Data Contracts."""

import pytest
from pydantic import ValidationError

from nemawashi.core.models import (
    MODEL_PRICING_GRID,
    AgentProposal,
    AuditRecord,
    ModelPricing,
    Resolution,
    StructuredAgentVote,
    UsageMetadata,
)


def test_structured_agent_vote_valid():
    """Verify that StructuredAgentVote accepts valid inputs."""
    vote = StructuredAgentVote(
        stakeholder_id="security",
        vote="APPROVE",
        risk_tags=["credential-review"],
        mitigation_requirements=["Require mTLS"],
    )
    assert vote.stakeholder_id == "security"
    assert vote.vote == "APPROVE"
    assert vote.risk_tags == ["credential-review"]
    assert vote.mitigation_requirements == ["Require mTLS"]


def test_structured_agent_vote_extra_forbidden():
    """Verify that arbitrary fields are forbidden to prevent context dilution."""
    with pytest.raises(ValidationError):
        StructuredAgentVote(
            stakeholder_id="compliance",
            vote="APPROVE",
            arbitrary_commentary="Unstructured conversational text",  # type: ignore
        )


def test_structured_agent_vote_invalid_stakeholder():
    """Verify that only authorized stakeholder IDs are accepted."""
    with pytest.raises(ValidationError):
        StructuredAgentVote(
            stakeholder_id="unauthorized_agent",  # type: ignore
            vote="APPROVE",
        )


def test_structured_agent_vote_invalid_vote():
    """Verify that only APPROVE, REJECT, or MITIGATE are valid votes."""
    with pytest.raises(ValidationError):
        StructuredAgentVote(
            stakeholder_id="sre",
            vote="MAYBE",  # type: ignore
        )


def test_agent_proposal_defaults_and_validation():
    """Verify proposal instantiation and default parameters."""
    proposal = AgentProposal(
        proposal_id="prop-123",
        proposing_agent="agent-worker",
        action_type="scale_cluster",
        action_description="Scale worker nodes from 2 to 4",
        target_resource="k8s-worker-pool",
        estimated_cost_usd=50.0,
        estimated_blast_radius=25,
    )
    assert proposal.proposal_id == "prop-123"
    assert proposal.estimated_cost_usd == 50.0
    assert proposal.estimated_blast_radius == 25
    assert isinstance(proposal.parameters, dict)
    assert proposal.timestamp is not None


def test_resolution_model():
    """Verify resolution model integrity."""
    resolution = Resolution(
        proposal_id="prop-123",
        verdict="CONDITIONAL_ALIGNMENT",
        composite_risk_score=45,
        mandatory_mitigations=["Dry-run first"],
        requires_human_approval=False,
        requires_revision=False,
        summary="Approved with dry-run condition",
    )
    assert resolution.verdict == "CONDITIONAL_ALIGNMENT"
    assert resolution.composite_risk_score == 45
    assert not resolution.requires_human_approval


def test_usage_metadata_and_pricing():
    """Verify FinOps token and cost modeling."""
    usage = UsageMetadata(
        prompt_tokens=1000,
        completion_tokens=200,
        total_tokens=1200,
        cost_usd=0.000135,
    )
    assert usage.prompt_tokens == 1000
    assert usage.completion_tokens == 200
    assert usage.total_tokens == 1200
    assert usage.cost_usd == 0.000135

    pricing = MODEL_PRICING_GRID["gemini-2.5-flash"]
    cost = pricing.calculate_cost(prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert cost == 0.375  # 0.075 + 0.30


def test_audit_record_validation():
    """Verify AuditRecord schema integrity and extra forbidden constraint."""
    record = AuditRecord(
        index=0,
        timestamp="2026-11-08T00:00:00Z",
        proposal_id="p-001",
        action_type="deploy",
        verdict="UNANIMOUS_CONSENSUS",
        execution_permitted=True,
        composite_risk_score=10,
        stakeholder_votes={"security": {"vote": "APPROVE"}},
        mitigations=[],
        deliberation_round=1,
        prompt_tokens=250,
        completion_tokens=50,
        total_cost_usd=0.00003,
        previous_hash="0" * 64,
        record_hash="abc123hash",
    )
    assert record.index == 0
    assert record.prompt_tokens == 250
    assert record.total_cost_usd == 0.00003

    # Extra fields must be forbidden
    with pytest.raises(ValidationError):
        AuditRecord(
            index=0,
            timestamp="2026-11-08T00:00:00Z",
            proposal_id="p-001",
            action_type="deploy",
            verdict="UNANIMOUS_CONSENSUS",
            execution_permitted=True,
            composite_risk_score=10,
            previous_hash="0" * 64,
            record_hash="abc123hash",
            illegal_extra="hack",  # type: ignore
        )


def test_structured_agent_vote_frozen():
    """Verify that StructuredAgentVote contract remains strictly frozen against in-place mutations."""
    vote = StructuredAgentVote(
        stakeholder_id="security",
        vote="APPROVE",
        risk_tags=["iam"],
    )
    with pytest.raises(ValidationError):
        vote.vote = "REJECT"  # type: ignore

