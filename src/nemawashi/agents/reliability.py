"""SRE Sentinel (Reliability) Agent."""

from typing import Dict, Optional
from nemawashi.agents.base import BaseGovernanceAgent
from nemawashi.core.models import AgentProposal, StructuredAgentVote


class SRESentinelAgent(BaseGovernanceAgent):
    """Enforces reliability, blast radius boundaries, and rollback safety."""

    def __init__(self):
        super().__init__(
            stakeholder_id="sre",
            prompt_file="sre_stakeholder.md",
        )

    def _evaluate_offline(
        self,
        proposal: AgentProposal,
        prior_votes: Optional[Dict[str, StructuredAgentVote]] = None,
    ) -> StructuredAgentVote:
        blast_radius = proposal.estimated_blast_radius
        desc = proposal.action_description.lower()
        risk_tags = []
        mitigations = []
        vote_verdict = "APPROVE"

        # Check prior votes
        if prior_votes:
            for sid, vote in prior_votes.items():
                if vote.vote == "REJECT":
                    risk_tags.append(f"upstream-rejection-by-{sid}")
                    vote_verdict = "REJECT"

        if blast_radius > 70:
            risk_tags.append("high-blast-radius")
            mitigations.append("ENFORCE: Implement 5% canary deployment with 15-minute soak and metric rollback threshold")
            if vote_verdict != "REJECT":
                vote_verdict = "MITIGATE"

        if "migration" in desc or "schema" in desc or "ddl" in desc:
            risk_tags.append("database-schema-mutation")
            mitigations.append("ENFORCE: Create pre-execution snapshot and automated backward-compatible rollback script")
            if vote_verdict != "REJECT":
                vote_verdict = "MITIGATE"

        return StructuredAgentVote(
            stakeholder_id="sre",
            vote=vote_verdict,
            risk_tags=risk_tags,
            mitigation_requirements=mitigations,
        )
