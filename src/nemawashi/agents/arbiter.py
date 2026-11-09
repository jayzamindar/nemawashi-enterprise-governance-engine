"""Consensus Arbiter Agent.

Synthesizes structured votes from all stakeholders into an authoritative Resolution.
"""

from typing import Dict, List, Optional
from nemawashi.core.models import AgentProposal, Resolution, StructuredAgentVote


class ConsensusArbiterAgent:
    """Consensus Arbiter synthesizing sequential stakeholder deliberation into a final verdict."""

    def synthesize(
        self,
        proposal: AgentProposal,
        votes: Dict[str, StructuredAgentVote],
        current_round: int = 1,
        max_rounds: int = 3,
        requires_revision: bool = False,
    ) -> Resolution:
        """Synthesize votes into a definitive Resolution object."""
        # 1. Check for hard rejections
        rejections = [sid for sid, v in votes.items() if v.vote == "REJECT"]
        if rejections:
            summary = f"Consensus VETO: Rejection issued by {', '.join(rejections)}."
            return Resolution(
                proposal_id=proposal.proposal_id,
                verdict="CONSENSUS_VETO",
                composite_risk_score=95,
                mandatory_mitigations=[],
                requires_human_approval=False,
                requires_revision=False,
                summary=summary,
            )

        # 2. Collect and deduplicate mitigations and risk tags
        all_mitigations: List[str] = []
        all_risk_tags: List[str] = []
        mitigate_count = 0

        for sid, v in votes.items():
            if v.vote == "MITIGATE":
                mitigate_count += 1
            for m in v.mitigation_requirements:
                if m not in all_mitigations:
                    all_mitigations.append(m)
            for t in v.risk_tags:
                if t not in all_risk_tags:
                    all_risk_tags.append(t)

        # 3. Calculate composite risk score (0-100)
        base_risk = proposal.estimated_blast_radius * 0.4
        cost_factor = min(40.0, (proposal.estimated_cost_usd / 500.0) * 20.0)
        tag_factor = min(30.0, len(all_risk_tags) * 5.0)
        composite_risk = int(min(100, round(base_risk + cost_factor + tag_factor)))

        # 4. Check for Human-in-the-Loop escalation conditions
        # Cost >= $500, Blast >= 80, or composite risk >= 75
        needs_hitl = (
            proposal.estimated_cost_usd >= 500.0
            or proposal.estimated_blast_radius >= 80
            or composite_risk >= 75
            or any("hipaa" in t or "pci" in t for t in all_risk_tags)
        )

        if needs_hitl:
            summary = (
                f"HITL Escalation: Proposal parameters require executive human authorization "
                f"(Cost: ${proposal.estimated_cost_usd:.2f}, Blast Radius: {proposal.estimated_blast_radius}, "
                f"Composite Risk: {composite_risk}/100)."
            )
            return Resolution(
                proposal_id=proposal.proposal_id,
                verdict="HUMAN_IN_THE_LOOP_ESCALATION",
                composite_risk_score=composite_risk,
                mandatory_mitigations=all_mitigations,
                requires_human_approval=True,
                requires_revision=False,
                summary=summary,
            )

        # 5. Conditional Alignment (Mitigations required)
        if mitigate_count > 0:
            summary = (
                f"Conditional Alignment: Consensus reached subject to {len(all_mitigations)} "
                f"mandatory safety constraints across {mitigate_count} stakeholders."
            )
            return Resolution(
                proposal_id=proposal.proposal_id,
                verdict="CONDITIONAL_ALIGNMENT",
                composite_risk_score=composite_risk,
                mandatory_mitigations=all_mitigations,
                requires_human_approval=False,
                requires_revision=requires_revision,
                summary=summary,
            )

        # 6. Unanimous Consensus
        summary = (
            f"Unanimous Consensus: All stakeholders approved with zero mitigation requirements "
            f"(Composite Risk: {composite_risk}/100)."
        )
        return Resolution(
            proposal_id=proposal.proposal_id,
            verdict="UNANIMOUS_CONSENSUS",
            composite_risk_score=composite_risk,
            mandatory_mitigations=[],
            requires_human_approval=False,
            requires_revision=False,
            summary=summary,
        )
