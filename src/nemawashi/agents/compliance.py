"""Compliance & Legal Arbiter Agent."""

from typing import Dict, Optional
from nemawashi.agents.base import BaseGovernanceAgent
from nemawashi.core.models import AgentProposal, StructuredAgentVote


class ComplianceArbiterAgent(BaseGovernanceAgent):
    """Enforces regulatory compliance (GDPR, HIPAA, SOC 2, PCI-DSS) and auditability."""

    def __init__(self):
        super().__init__(
            stakeholder_id="compliance",
            prompt_file="compliance_stakeholder.md",
        )

    def _evaluate_offline(
        self,
        proposal: AgentProposal,
        prior_votes: Optional[Dict[str, StructuredAgentVote]] = None,
    ) -> StructuredAgentVote:
        target = proposal.target_resource.lower()
        desc = proposal.action_description.lower()

        risk_tags = []
        mitigations = []
        vote_verdict = "APPROVE"

        # Check prior security vote
        if prior_votes and "security" in prior_votes:
            sec_vote = prior_votes["security"]
            if "unrestricted-ingress" in sec_vote.risk_tags:
                risk_tags.append("compliance-audit-risk-from-network-exposure")
                mitigations.append("ENFORCE: Mandate comprehensive CloudTrail and VPC Flow Logging")
                vote_verdict = "MITIGATE"

        # Check for PII / Healthcare / Cardholder data
        if any(w in target or w in desc for w in ["patient", "hipaa", "medical"]):
            risk_tags.append("hipaa-protected-health-information")
            mitigations.append("ENFORCE: Require field-level AES-256 encryption and BAA compliance attestation")
            vote_verdict = "MITIGATE"

        if any(w in target or w in desc for w in ["card", "pci", "payment", "cvv"]):
            risk_tags.append("pci-dss-cardholder-scope")
            mitigations.append("ENFORCE: Tokenize cardholder data and prohibit raw transmission")
            vote_verdict = "MITIGATE"

        if any(w in target or w in desc for w in ["user", "pii", "gdpr", "email"]):
            risk_tags.append("gdpr-data-privacy")
            mitigations.append("ENFORCE: Retain audit trail with anonymized identifiers for GDPR Art 30")
            if vote_verdict != "REJECT":
                vote_verdict = "MITIGATE"

        return StructuredAgentVote(
            stakeholder_id="compliance",
            vote=vote_verdict,
            risk_tags=risk_tags,
            mitigation_requirements=mitigations,
        )
