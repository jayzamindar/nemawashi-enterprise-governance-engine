"""High-level Orchestrator and Client Interface for Nemawashi Governance Engine."""

from pathlib import Path
from typing import Optional
from nemawashi.audit.ledger import commit_chained_audit_ledger_node, verify_ledger_chain
from nemawashi.core.graph import build_nemawashi_graph, load_suspended_state
from nemawashi.core.models import AgentProposal
from nemawashi.core.state import NemawashiState, create_initial_state


class NemawashiEngine:
    """High-level facade for executing multi-agent governance deliberations."""

    def __init__(self, max_rounds: int = 3):
        self.max_rounds = max_rounds
        self._compiled_graph = build_nemawashi_graph().compile()

    def evaluate_proposal(
        self,
        proposal: AgentProposal,
        human_approved: Optional[bool] = None,
    ) -> NemawashiState:
        """Run the complete sequential Nemawashi governance deliberation on a proposal."""
        initial_state = create_initial_state(
            proposal=proposal,
            max_rounds=self.max_rounds,
            human_approved=human_approved,
        )

        # Omit 'votes' channel from initial invoke write to prevent writing an initial list
        # to the strictly typed append_vote channel reducer
        invoke_state = {k: v for k, v in initial_state.items() if k != "votes"}
        final_state: NemawashiState = self._compiled_graph.invoke(invoke_state)
        return final_state

    def resume_proposal(
        self,
        proposal_id: str,
        approved: bool,
        rationale: str = "Operator decision supplied via gateway callback",
        storage_dir: Optional[Path] = None,
    ) -> NemawashiState:
        """Resume execution of a suspended HITL proposal.

        Loads serialized state from local storage, injects operator decision and rationale,
        and seamlessly triggers execution resumption through the terminal audit ledger node.
        """
        state = load_suspended_state(proposal_id, storage_dir=storage_dir)
        state["human_approved"] = approved
        state["human_rationale"] = rationale
        state["execution_permitted"] = approved
        state["suspended_for_hitl"] = False

        # Seal the resumed deliberation into the immutable terminal audit ledger
        ledger_update = commit_chained_audit_ledger_node(state)
        state["audit_committed"] = ledger_update["audit_committed"]
        state["audit_record_hash"] = ledger_update["audit_record_hash"]
        if "audit_ledger" in ledger_update:
            state["audit_ledger"] = (
                list(state.get("audit_ledger", [])) + ledger_update["audit_ledger"]
            )

        # Remove the suspended state file from disk upon successful resumption (TRD-5.2)
        from nemawashi.core.graph import SUSPENDED_STATES_DIR

        target_dir = storage_dir or SUSPENDED_STATES_DIR
        state_file = target_dir / f"{proposal_id}.json"
        if state_file.exists():
            try:
                state_file.unlink()
            except OSError:
                pass

        return state

    def verify_audit_ledger(self) -> tuple[bool, str]:
        """Verify cryptographic integrity of the audit ledger."""
        return verify_ledger_chain()
