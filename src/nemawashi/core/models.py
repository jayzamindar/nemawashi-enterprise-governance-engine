"""Core Pydantic models for the Nemawashi Enterprise Multi-Agent Governance Engine.

Enforces strict structured memory contracts to prevent context dilution,
persona drift, and unconstrained token consumption, with real-time FinOps token observability.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
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
    risk_tags: List[str] = Field(
        default_factory=list,
        description="Categorical tags identifying concrete risk vectors (e.g. ['privilege-escalation', 'data-exfiltration']).",
    )
    mitigation_requirements: List[str] = Field(
        default_factory=list,
        description="Exact technical guardrails or constraints required for conditional execution.",
    )


class UsageMetadata(BaseModel):
    """Token consumption and financial cost metadata for an agent turn."""

    model_config = ConfigDict(extra="ignore", frozen=True)

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
MODEL_PRICING_GRID: Dict[str, ModelPricing] = {
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


class AgentProposal(BaseModel):
    """Proposal submitted by an operational agent requesting execution permission."""

    model_config = ConfigDict(extra="ignore")

    proposal_id: str = Field(
        ..., min_length=1, description="Unique UUID or identifier for the proposal"
    )
    proposing_agent: str = Field(
        ..., min_length=1, description="Agent name or service initiating the request"
    )
    action_type: str = Field(
        ...,
        min_length=1,
        description="Action classification (e.g., 'database_migration', 'iam_policy_update')",
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
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Execution parameters or payload dictionary"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 creation timestamp",
    )


class Resolution(BaseModel):
    """Consensus resolution synthesized by the Consensus Arbiter."""

    model_config = ConfigDict(extra="ignore")

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
    mandatory_mitigations: List[str] = Field(
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

    model_config = ConfigDict(extra="forbid")

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
    stakeholder_votes: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Serialized StructuredAgentVote map for all stakeholders",
    )
    mitigations: List[str] = Field(
        default_factory=list, description="Enforced mitigations"
    )
    human_approval: Optional[Dict[str, Any]] = Field(
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
