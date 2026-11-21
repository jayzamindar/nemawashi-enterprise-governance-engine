"""Tests for Deterministic Policy Pre-check Engine."""

import json

import pytest
from pydantic import ValidationError

from nemawashi.core.models import AgentProposal
from nemawashi.policies.policy_engine import (
    CatalogNotFoundError,
    EnterpriseRulesConfig,
    evaluate_proposal_policies,
    load_enterprise_rules,
    normalize_policy_text,
)


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


def test_missing_catalog_fails_closed(tmp_path):
    """Verify missing enterprise_rules.json raises CatalogNotFoundError and fails closed."""
    missing_path = tmp_path / "nonexistent_rules.json"
    with pytest.raises(CatalogNotFoundError, match="not found"):
        load_enterprise_rules(missing_path)

    proposal = AgentProposal(
        proposal_id="p-missing-cat",
        proposing_agent="agent-infra",
        action_type="scale_cache",
        action_description="Scale redis cache replicas",
        target_resource="cache-redis-01",
        estimated_cost_usd=20.0,
        estimated_blast_radius=10,
    )
    result = evaluate_proposal_policies(proposal, rules_path=missing_path)
    assert result.passed is False
    assert any("CATALOG_MISSING_OR_CORRUPT" in v for v in result.violations)


def test_corrupt_or_schema_invalid_catalog_fails_closed(tmp_path):
    """Verify corrupt JSON or extra/invalid keys fail closed with CatalogNotFoundError."""
    corrupt_path = tmp_path / "corrupt_rules.json"
    corrupt_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(CatalogNotFoundError, match="invalid or unreadable"):
        load_enterprise_rules(corrupt_path)

    proposal = AgentProposal(
        proposal_id="p-corrupt-cat",
        proposing_agent="agent-infra",
        action_type="scale_cache",
        action_description="Scale redis cache replicas",
        target_resource="cache-redis-01",
    )
    corrupt_result = evaluate_proposal_policies(proposal, rules_path=corrupt_path)
    assert corrupt_result.passed is False
    assert any("CATALOG_MISSING_OR_CORRUPT" in v for v in corrupt_result.violations)

    extra_key_path = tmp_path / "extra_key_rules.json"
    extra_key_path.write_text(
        json.dumps(
            {
                "max_allowed_cost_usd": 5000.0,
                "hitl_cost_threshold_usd": 500.0,
                "hitl_blast_radius_threshold": 80,
                "prohibited_actions": [],
                "prohibited_target_substrings": [],
                "sensitive_resources": [],
                "unexpected_key": 123,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(CatalogNotFoundError, match="invalid or unreadable"):
        load_enterprise_rules(extra_key_path)

    extra_result = evaluate_proposal_policies(proposal, rules_path=extra_key_path)
    assert extra_result.passed is False
    assert any("CATALOG_MISSING_OR_CORRUPT" in v for v in extra_result.violations)


def test_enterprise_rules_config_is_strict_and_frozen():
    """Verify EnterpriseRulesConfig forbids extra fields and is immutable."""
    with pytest.raises(ValidationError):
        EnterpriseRulesConfig(
            max_allowed_cost_usd=5000.0,
            hitl_cost_threshold_usd=500.0,
            hitl_blast_radius_threshold=80,
            unknown_field=True,  # type: ignore[call-arg]
        )


def test_nfkc_homoglyph_normalization_blocks_bypass():
    """Verify fullwidth NFKC homoglyphs cannot bypass protected or sensitive target checks."""
    # Fullwidth "prod-primary-db-01"
    protected_proposal = AgentProposal(
        proposal_id="p-nfkc-protected",
        proposing_agent="agent-worker",
        action_type="restart_node",
        action_description="Restart node using fullwidth target",
        target_resource="ｐｒｏｄ－ｐｒｉｍａｒｙ－ｄｂ－０１",
        estimated_cost_usd=10.0,
        estimated_blast_radius=10,
    )
    protected_result = evaluate_proposal_policies(protected_proposal)
    assert protected_result.passed is False
    assert any("PROTECTED_RESOURCE" in v for v in protected_result.violations)

    # Fullwidth "pci-dss-cardholder-env"
    sensitive_proposal = AgentProposal(
        proposal_id="p-nfkc-sensitive",
        proposing_agent="agent-worker",
        action_type="restart_node",
        action_description="Restart node in fullwidth sensitive target",
        target_resource="ｐｃｉ－ｄｓｓ－ｃａｒｄｈｏｌｄｅｒ－ｅｎｖ",
        estimated_cost_usd=10.0,
        estimated_blast_radius=10,
    )
    sensitive_result = evaluate_proposal_policies(sensitive_proposal)
    assert sensitive_result.passed is True
    assert sensitive_result.requires_hitl is True
    assert any("SENSITIVE_RESOURCE_ACCESS" in r for r in sensitive_result.hitl_reasons)

    assert (
        normalize_policy_text("  ＤＲＯＰ＿ＰＲＯＤＵＣＴＩＯＮ＿ＤＡＴＡＢＡＳＥ  ")
        == "drop_production_database"
    )
