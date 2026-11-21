"""Core Pydantic models for the Nemawashi Enterprise Multi-Agent Governance Engine.

Enforces strict structured memory contracts to prevent context dilution,
persona drift, and unconstrained token consumption, with real-time FinOps token observability.
"""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StructuredAgentVote(BaseModel):
    """Structured vote emitted by each stakeholder agent in the sequential Nemawashi circle.

    Prevents context dilution and eliminates arbitrary conversational string commentary.
    Configured as the native Gemini response_schema. Contract is frozen and strictly typed.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    stakeholder_id: Literal["security", "compliance", "finops", "sre"] = Field(
        ...,
        description="Identifier of the reviewing stakeholder persona: security, compliance, finops, or sre.",
    )
    vote: Literal["APPROVE", "REJECT", "MITIGATE"] = Field(
        ...,
        description="Explicit structured verdict: APPROVE, REJECT, or MITIGATE.",
    )
    risk_tags: list[str] = Field(
        default_factory=list,
        description="Categorical tags identifying concrete risk vectors (e.g. ['privilege-escalation', 'data-exfiltration']).",
    )
    mitigation_requirements: list[str] = Field(
        default_factory=list,
        description="Exact technical guardrails or constraints required for conditional execution.",
    )


class UsageMetadata(BaseModel):
    """Token consumption and financial cost metadata for an agent turn."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt_tokens: int = Field(default=0, ge=0, description="Input tokens consumed")
    completion_tokens: int = Field(
        default=0, ge=0, description="Output tokens generated"
    )
    total_tokens: int = Field(default=0, ge=0, description="Total tokens consumed")
    cost_usd: float = Field(
        default=0.0, ge=0.0, description="Estimated financial cost in USD for this turn"
    )


class ModelPricing(BaseModel):
    """Pricing configuration for a given LLM model (per 1,000,000 tokens)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input_cost_per_million: float = Field(
        ..., ge=0.0, description="Cost per million input tokens"
    )
    output_cost_per_million: float = Field(
        ..., ge=0.0, description="Cost per million output tokens"
    )

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate dynamic execution cost based on model token rates."""
        input_cost = (prompt_tokens / 1_000_000.0) * self.input_cost_per_million
        output_cost = (completion_tokens / 1_000_000.0) * self.output_cost_per_million
        return round(input_cost + output_cost, 6)


# Gemini Model Pricing Grid (Default Gemini 2.5 Flash / Pro tier)
MODEL_PRICING_GRID: dict[str, ModelPricing] = {
    "gemini-2.5-flash": ModelPricing(
        input_cost_per_million=0.075, output_cost_per_million=0.30
    ),
    "gemini-1.5-pro": ModelPricing(
        input_cost_per_million=1.25, output_cost_per_million=5.00
    ),
    "offline-mock": ModelPricing(
        input_cost_per_million=0.075, output_cost_per_million=0.30
    ),
}


ActionType = Literal[
    "api_gateway_deploy",
    "cache_cluster_scale",
    "cluster_provision",
    "compute_cluster_expansion",
    "ddl_migration",
    "delete_backup",
    "delete_root_iam_credentials",
    "deploy",
    "deploy_app",
    "disable_cloudtrail_logging",
    "drop_production_database",
    "escalate",
    "gpu_cluster",
    "iam_role_elevation",
    "iterative_action",
    "modify_security_group_allow_all_ingress_0_0_0_0",
    "nodes_add",
    "open_firewall",
    "open_firewall_rule",
    "process_patient_records",
    "provision_env",
    "provision_expensive_fleet",
    "provision_gpu_cluster",
    "provision_gpu_fleet",
    "provision_gpus",
    "provision_nodes",
    "restart_node",
    "restart_service",
    "scale",
    "scale_cache",
    "scale_cluster",
    "scale_down",
    "scale_up",
    "schema_migration_ddl",
    "terminate_payment_gateway_cluster",
]


class HumanApprovalRecord(BaseModel):
    """Frozen operator decision record for HITL-escalated proposals."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    approved: bool = Field(
        ..., description="Operator decision: True to authorize, False to veto"
    )
    rationale: str = Field(
        default="", description="Written justification for operator decision"
    )


class AgentProposal(BaseModel):
    """Proposal submitted by an operational agent requesting execution permission."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^[a-zA-Z0-9_-]{1,128}$",
        description="Unique UUID or identifier for the proposal",
    )
    proposing_agent: str = Field(
        ..., min_length=1, description="Agent name or service initiating the request"
    )
    action_type: ActionType = Field(
        ...,
        description="Validated action classification allowlist",
    )
    action_description: str = Field(
        ...,
        min_length=1,
        description="Detailed technical description of the proposed action",
    )
    target_resource: str = Field(
        ...,
        min_length=1,
        description="Target cloud infrastructure, database, or API resource",
    )
    estimated_cost_usd: float = Field(
        default=0.0, ge=0.0, description="Estimated financial cost in USD"
    )
    estimated_blast_radius: int = Field(
        default=0, ge=0, le=100, description="Estimated blast radius score (0-100)"
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Execution parameters or payload dictionary"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO 8601 creation timestamp",
    )


class Resolution(BaseModel):
    """Consensus resolution synthesized by the Consensus Arbiter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: str = Field(
        ..., min_length=1, description="Associated proposal identifier"
    )
    verdict: Literal[
        "UNANIMOUS_CONSENSUS",
        "CONDITIONAL_ALIGNMENT",
        "HUMAN_IN_THE_LOOP_ESCALATION",
        "CONSENSUS_VETO",
    ] = Field(..., description="Synthesized multi-agent governance verdict")
    composite_risk_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Aggregate risk score normalized across all stakeholders (0-100)",
    )
    mandatory_mitigations: list[str] = Field(
        default_factory=list,
        description="Deduplicated list of mandatory mitigations required prior to execution",
    )
    requires_human_approval: bool = Field(
        default=False,
        description="Flag indicating whether high risk/cost necessitates human executive intervention",
    )
    requires_revision: bool = Field(
        default=False,
        description="Flag indicating if the proposal should loop back for another deliberation iteration",
    )
    summary: str = Field(
        ...,
        min_length=1,
        description="Executive governance summary explaining the final alignment or veto rationale",
    )


class AuditRecord(BaseModel):
    """Cryptographically chained ledger record entry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(..., ge=0, description="Monotonically increasing block index")
    timestamp: str = Field(
        ..., min_length=1, description="ISO 8601 timestamp of commitment"
    )
    proposal_id: str = Field(..., min_length=1, description="Proposal identifier")
    action_type: str = Field(..., min_length=1, description="Action type")
    verdict: str = Field(..., min_length=1, description="Final governance verdict")
    execution_permitted: bool = Field(
        ..., description="Whether execution was authorized"
    )
    composite_risk_score: int = Field(
        ..., ge=0, le=100, description="Final composite risk score"
    )
    stakeholder_votes: dict[str, StructuredAgentVote] = Field(
        default_factory=dict,
        description="Serialized StructuredAgentVote map for all stakeholders",
    )
    mitigations: list[str] = Field(
        default_factory=list, description="Enforced mitigations"
    )
    human_approval: HumanApprovalRecord | None = Field(
        default=None,
        description="Operator decision and rationale if human-in-the-loop was triggered",
    )
    deliberation_round: int = Field(
        default=1, ge=1, description="Round number when resolution was finalized"
    )
    prompt_tokens: int = Field(
        default=0, ge=0, description="Cumulative input tokens across all agent turns"
    )
    completion_tokens: int = Field(
        default=0, ge=0, description="Cumulative output tokens across all agent turns"
    )
    total_cost_usd: float = Field(
        default=0.0, ge=0.0, description="Accrued running financial cost in USD"
    )
    cache_hit: bool = Field(
        default=False,
        description="Whether this deliberation was satisfied via semantic vector cache",
    )
    previous_hash: str = Field(
        ..., description="SHA-256 hash of the preceding ledger record"
    )
    record_hash: str = Field(..., description="SHA-256 hash of this complete block")
