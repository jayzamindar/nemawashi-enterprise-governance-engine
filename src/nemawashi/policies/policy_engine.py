"""Deterministic Enterprise Policy Pre-check Engine.

Fast evaluation of non-negotiable enterprise constraints (hard spend caps,
prohibited destructive operations, sensitive target isolation).
"""

import json
import unicodedata
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from nemawashi.core.models import AgentProposal

DEFAULT_RULES_PATH = Path(__file__).parent / "enterprise_rules.json"


class CatalogNotFoundError(RuntimeError):
    """Raised when the deterministic policy catalog is missing, unreadable, or schema-invalid."""


class EnterpriseRulesConfig(BaseModel):
    """Strict schema for deterministic enterprise governance rules."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_allowed_cost_usd: float = Field(..., ge=0.0)
    hitl_cost_threshold_usd: float = Field(..., ge=0.0)
    hitl_blast_radius_threshold: int = Field(..., ge=0, le=100)
    prohibited_actions: list[str] = Field(default_factory=list)
    prohibited_target_substrings: list[str] = Field(default_factory=list)
    sensitive_resources: list[str] = Field(default_factory=list)


class PolicyEvaluationResult(BaseModel):
    """Result of policy pre-check."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    passed: bool = Field(
        ..., description="Whether the proposal clears all hard policy vetoes"
    )
    violations: list[str] = Field(
        default_factory=list, description="List of specific violated policy rules"
    )
    requires_hitl: bool = Field(
        default=False, description="Whether policy mandates human executive sign-off"
    )
    hitl_reasons: list[str] = Field(
        default_factory=list, description="Triggers requiring human intervention"
    )


def normalize_policy_text(value: str) -> str:
    """Apply Unicode NFKC normalization, whitespace trimming, and casefolding."""
    return unicodedata.normalize("NFKC", value).strip().casefold()


def load_enterprise_rules(rules_path: Path | None = None) -> EnterpriseRulesConfig:
    """Load and strictly validate the deterministic enterprise policy catalog.

    Fails closed by raising CatalogNotFoundError if the catalog is missing,
    unreadable, invalid JSON, or fails EnterpriseRulesConfig validation.
    """
    path = rules_path or DEFAULT_RULES_PATH
    if not path.exists() or not path.is_file():
        raise CatalogNotFoundError(f"Policy catalog not found at {path}")

    try:
        raw_text = path.read_text(encoding="utf-8")
        raw_data = json.loads(raw_text)
        return EnterpriseRulesConfig.model_validate(raw_data)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        raise CatalogNotFoundError(
            f"Policy catalog invalid or unreadable at {path}: {exc}"
        ) from exc


def evaluate_proposal_policies(
    proposal: AgentProposal,
    rules_path: Path | None = None,
) -> PolicyEvaluationResult:
    """Evaluate an AgentProposal against deterministic enterprise governance policies."""
    try:
        rules = load_enterprise_rules(rules_path)
    except CatalogNotFoundError as exc:
        return PolicyEvaluationResult(
            passed=False,
            violations=[f"CATALOG_MISSING_OR_CORRUPT: {exc}"],
            requires_hitl=False,
            hitl_reasons=[],
        )

    violations: list[str] = []
    hitl_reasons: list[str] = []

    # 1. Prohibited Actions (Hard Veto)
    action_type = normalize_policy_text(proposal.action_type)
    prohibited_actions = {
        normalize_policy_text(act) for act in rules.prohibited_actions
    }
    if action_type in prohibited_actions:
        violations.append(
            f"PROHIBITED_ACTION: Action '{proposal.action_type}' is on the enterprise blacklisted operations registry."
        )

    # 2. Prohibited Target Substrings (Hard Veto)
    target = normalize_policy_text(proposal.target_resource)
    for sub in rules.prohibited_target_substrings:
        norm_sub = normalize_policy_text(sub)
        if norm_sub and norm_sub in target:
            violations.append(
                f"PROTECTED_RESOURCE: Target '{proposal.target_resource}' contains protected identifier '{sub}'."
            )

    # 3. Maximum Allowed Cost (Hard Veto)
    if proposal.estimated_cost_usd > rules.max_allowed_cost_usd:
        violations.append(
            f"BUDGET_CEILING_BREACH: Estimated cost ${proposal.estimated_cost_usd:.2f} exceeds absolute platform ceiling of ${rules.max_allowed_cost_usd:.2f}."
        )

    # 4. HITL Escalation Triggers
    if proposal.estimated_cost_usd >= rules.hitl_cost_threshold_usd:
        hitl_reasons.append(
            f"FINANCIAL_ESCALATION: Cost ${proposal.estimated_cost_usd:.2f} exceeds HITL threshold ${rules.hitl_cost_threshold_usd:.2f}."
        )

    if proposal.estimated_blast_radius >= rules.hitl_blast_radius_threshold:
        hitl_reasons.append(
            f"BLAST_RADIUS_ESCALATION: Estimated blast radius {proposal.estimated_blast_radius}/100 exceeds threshold {rules.hitl_blast_radius_threshold}."
        )

    if any(
        norm_s in target
        for s in rules.sensitive_resources
        if (norm_s := normalize_policy_text(s))
    ):
        hitl_reasons.append(
            f"SENSITIVE_RESOURCE_ACCESS: Proposal targets high-compliance resource domain '{proposal.target_resource}'."
        )

    return PolicyEvaluationResult(
        passed=len(violations) == 0,
        violations=violations,
        requires_hitl=len(hitl_reasons) > 0,
        hitl_reasons=hitl_reasons,
    )
