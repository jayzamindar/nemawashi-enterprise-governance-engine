"""FinOps & Resource Arbiter Agent."""

from typing import Dict, Optional
from nemawashi.agents.base import BaseGovernanceAgent
from nemawashi.core.models import AgentProposal, StructuredAgentVote


class FinOpsArbiterAgent(BaseGovernanceAgent):
    """Enforces financial spend caps, quota management, and token unit economics."""

    def __init__(self):
        super().__init__(
            stakeholder_id="finops",
            prompt_file="finops_stakeholder.md",
        )

    def _evaluate_offline(
        self,
        proposal: AgentProposal,
        prior_votes: Optional[Dict[str, StructuredAgentVote]] = None,
    ) -> StructuredAgentVote:
        cost = proposal.estimated_cost_usd
        risk_tags = []
        mitigations = []
        vote_verdict = "APPROVE"

        # Check prior votes for expensive mitigations
        if prior_votes:
            for sid, vote in prior_votes.items():
                if "staging" in str(vote.mitigation_requirements).lower():
                    mitigations.append("ENFORCE: Auto-terminate staging instances after 2 hours to avoid idle billing")

        if cost > 1000.0:
            risk_tags.append("major-budget-consumption")
            mitigations.append("ENFORCE: Mandate spot/preemptible instances or compute savings plan")
            vote_verdict = "MITIGATE"
        elif cost > 300.0:
            risk_tags.append("moderate-budget-allocation")
            mitigations.append("ENFORCE: Attach FinOps CostCenter and Owner billing tags")
            vote_verdict = "MITIGATE"

        return StructuredAgentVote(
            stakeholder_id="finops",
            vote=vote_verdict,
            risk_tags=risk_tags,
            mitigation_requirements=mitigations,
        )
