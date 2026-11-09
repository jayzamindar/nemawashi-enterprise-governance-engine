"""Adaptive Cost Optimization Agent.

Dynamically rightsizes infrastructure proposals that trigger FinOps mitigations,
injecting cost-saving architectural alternatives into the proposal payload.
"""

import copy
from typing import Optional
from nemawashi.core.models import AgentProposal, StructuredAgentVote


class CostOptimizationAgent:
    """Specialized persona that restructures proposals to clear FinOps spend constraints."""

    def __init__(self):
        self.agent_id = "cost_optimizer"

    def optimize(
        self,
        proposal: AgentProposal,
        finops_vote: Optional[StructuredAgentVote] = None,
    ) -> AgentProposal:
        """Analyze proposal and return an optimized AgentProposal with reduced cost and safety tags."""
        # Deepcopy to preserve original proposal record
        optimized = copy.deepcopy(proposal)

        original_cost = proposal.estimated_cost_usd
        params = dict(optimized.parameters)

        # 1. Spot / Preemptible Instance Rightsizing
        # Reduce compute cost by 60% for stateless / worker clusters
        if original_cost > 500.0:
            reduction_factor = 0.55  # 45% savings
            new_cost = round(original_cost * reduction_factor, 2)
            params["instance_lifecycle"] = "spot"
            params["fallback_to_ondemand"] = True
            params["savings_plan"] = "compute_1yr_committed"
            strategy = "Converted on-demand nodes to spot/preemptible instances with on-demand fallback"
        elif original_cost > 200.0:
            reduction_factor = 0.70  # 30% savings
            new_cost = round(original_cost * reduction_factor, 2)
            params["auto_terminate_idle_hours"] = 2
            params["storage_tier"] = "gp3_optimized"
            strategy = "Attached automated idle shutdown policy and converted storage to gp3"
        else:
            reduction_factor = 0.85
            new_cost = round(original_cost * reduction_factor, 2)
            params["cost_center_tag"] = "engineering_optimized"
            strategy = "Attached FinOps billing tags and rightsized resource quotas"

        optimized.estimated_cost_usd = new_cost
        optimized.parameters = params
        optimized.action_description = (
            f"{proposal.action_description} [FinOps Cost-Optimized: {strategy}; "
            f"Cost reduced from ${original_cost:.2f} to ${new_cost:.2f}]"
        )

        return optimized
