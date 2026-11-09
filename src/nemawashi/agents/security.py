"""Security Guardian Agent."""

from typing import Dict, Optional
from nemawashi.agents.base import BaseGovernanceAgent
from nemawashi.core.models import AgentProposal, StructuredAgentVote


class SecurityGuardianAgent(BaseGovernanceAgent):
    """Enforces zero-trust, privilege boundaries, and injection defense."""

    def __init__(self):
        super().__init__(
            stakeholder_id="security",
            prompt_file="security_stakeholder.md",
        )

    def _evaluate_offline(
        self,
        proposal: AgentProposal,
        prior_votes: Optional[Dict[str, StructuredAgentVote]] = None,
    ) -> StructuredAgentVote:
        action = proposal.action_type.lower()
        desc = proposal.action_description.lower()
        target = proposal.target_resource.lower()

        risk_tags = []
        mitigations = []
        vote_verdict = "APPROVE"

        # Check for injection, root access, or ingress exposure
        if "0.0.0.0/0" in desc or "allow_all" in action:
            risk_tags.extend(["unrestricted-ingress", "network-exposure"])
            mitigations.append("ENFORCE: Restrict CIDR block to enterprise VPN only (e.g. 10.0.0.0/16)")
            vote_verdict = "MITIGATE"

        if "iam" in action or "role" in target or "privilege" in desc:
            risk_tags.append("iam-privilege-elevation")
            mitigations.append("ENFORCE: Apply time-bound session policy with max 1-hour TTL")
            if vote_verdict != "REJECT":
                vote_verdict = "MITIGATE"

        if "credential" in desc or "api_key" in desc or "secret" in target:
            risk_tags.append("credential-exposure-risk")
            mitigations.append("ENFORCE: Reference HashiCorp Vault or AWS Secrets Manager ARN; forbid plaintext secrets")
            if vote_verdict != "REJECT":
                vote_verdict = "MITIGATE"

        if proposal.estimated_blast_radius > 85:
            risk_tags.append("excessive-blast-radius")
            mitigations.append("ENFORCE: Execute in sandbox staging environment before production rollout")
            vote_verdict = "MITIGATE"

        return StructuredAgentVote(
            stakeholder_id="security",
            vote=vote_verdict,
            risk_tags=risk_tags,
            mitigation_requirements=mitigations,
        )
