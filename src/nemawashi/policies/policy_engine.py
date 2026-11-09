"""Deterministic Enterprise Policy Pre-check Engine.

Fast evaluation of non-negotiable enterprise constraints (hard spend caps,
prohibited destructive operations, sensitive target isolation).
"""

import json
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

from nemawashi.core.models import AgentProposal

DEFAULT_RULES_PATH = Path(__file__).parent / "enterprise_rules.json"


class PolicyEvaluationResult(BaseModel):
    """Result of policy pre-check."""

    passed: bool = Field(..., description="Whether the proposal clears all hard policy vetoes")
    violations: List[str] = Field(default_factory=list, description="List of specific violated policy rules")
    requires_hitl: bool = Field(default=False, description="Whether policy mandates human executive sign-off")
    hitl_reasons: List[str] = Field(default_factory=list, description="Triggers requiring human intervention")


def evaluate_proposal_policies(
    proposal: AgentProposal,
    rules_path: Optional[Path] = None,
) -> PolicyEvaluationResult:
    """Evaluate an AgentProposal against deterministic enterprise governance policies."""
    path = rules_path or DEFAULT_RULES_PATH
    if not path.exists():
        # Fallback default rules if configuration file is not found
        rules = {
            "max_allowed_cost_usd": 5000.0,
            "hitl_cost_threshold_usd": 500.0,
            "hitl_blast_radius_threshold": 80,
            "prohibited_actions": ["drop_production_database", "delete_root_iam_credentials"],
            "prohibited_target_substrings": ["prod-primary-db", "root-kms-key"],
        }
    else:
        with open(path, "r", encoding="utf-8") as f:
            rules = json.load(f)

    violations: List[str] = []
    hitl_reasons: List[str] = []

    # 1. Prohibited Actions (Hard Veto)
    action_type = proposal.action_type.lower().strip()
    if action_type in [act.lower() for act in rules.get("prohibited_actions", [])]:
        violations.append(
            f"PROHIBITED_ACTION: Action '{proposal.action_type}' is on the enterprise blacklisted operations registry."
        )

    # 2. Prohibited Target Substrings (Hard Veto)
    target = proposal.target_resource.lower().strip()
    for sub in rules.get("prohibited_target_substrings", []):
        if sub.lower() in target:
            violations.append(
                f"PROTECTED_RESOURCE: Target '{proposal.target_resource}' contains protected identifier '{sub}'."
            )

    # 3. Maximum Allowed Cost (Hard Veto)
    max_cost = float(rules.get("max_allowed_cost_usd", 5000.0))
    if proposal.estimated_cost_usd > max_cost:
        violations.append(
            f"BUDGET_CEILING_BREACH: Estimated cost ${proposal.estimated_cost_usd:.2f} exceeds absolute platform ceiling of ${max_cost:.2f}."
        )

    # 4. HITL Escalation Triggers
    hitl_cost = float(rules.get("hitl_cost_threshold_usd", 500.0))
    if proposal.estimated_cost_usd >= hitl_cost:
        hitl_reasons.append(
            f"FINANCIAL_ESCALATION: Cost ${proposal.estimated_cost_usd:.2f} exceeds HITL threshold ${hitl_cost:.2f}."
        )

    hitl_blast = int(rules.get("hitl_blast_radius_threshold", 80))
    if proposal.estimated_blast_radius >= hitl_blast:
        hitl_reasons.append(
            f"BLAST_RADIUS_ESCALATION: Estimated blast radius {proposal.estimated_blast_radius}/100 exceeds threshold {hitl_blast}."
        )

    sensitive_targets = [s.lower() for s in rules.get("sensitive_resources", [])]
    if any(s in target for s in sensitive_targets):
        hitl_reasons.append(
            f"SENSITIVE_RESOURCE_ACCESS: Proposal targets high-compliance resource domain '{proposal.target_resource}'."
        )

    passed = len(violations) == 0
    requires_hitl = len(hitl_reasons) > 0

    return PolicyEvaluationResult(
        passed=passed,
        violations=violations,
        requires_hitl=requires_hitl,
        hitl_reasons=hitl_reasons,
    )
