"""High-level Orchestrator and Client Interface for Nemawashi Governance Engine."""

from pathlib import Path
from typing import cast

from filelock import FileLock, Timeout

from nemawashi.audit.ledger import commit_chained_audit_ledger_node, verify_ledger_chain
from nemawashi.core.graph import (
    build_nemawashi_graph,
    get_suspended_states_dir,
    hitl_gatekeeper_routing,
    interactive_human_gatekeeper_node,
    load_suspended_state,
    validate_proposal_id,
)
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
        human_approved: bool | None = None,
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
        final_state = cast(NemawashiState, self._compiled_graph.invoke(invoke_state))
        return final_state

    def resume_proposal(
        self,
        proposal_id: str,
        approved: bool,
        rationale: str = "Operator decision supplied via gateway callback",
        storage_dir: Path | None = None,
    ) -> NemawashiState:
        """Resume execution of a suspended HITL proposal.

        Acquires a per-proposal_id FileLock around state loading, gatekeeper routing,
        terminal audit ledger commit, and suspended state cleanup to prevent TOCTOU races.
        """
        validate_proposal_id(proposal_id)
        target_dir = get_suspended_states_dir(storage_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        state_file = target_dir / f"{proposal_id}.json"
        lock_file = f"{state_file}.lock"

        try:
            with FileLock(lock_file, timeout=10.0):
                state = load_suspended_state(proposal_id, storage_dir=target_dir)
                state["human_approved"] = approved
                state["human_rationale"] = rationale

                # Route through interactive_human_gatekeeper_node before terminal ledger node
                gatekeeper_update = interactive_human_gatekeeper_node(state)
                state["human_approved"] = gatekeeper_update["human_approved"]
                state["execution_permitted"] = gatekeeper_update["execution_permitted"]
                state["human_rationale"] = gatekeeper_update["human_rationale"]
                state["suspended_for_hitl"] = gatekeeper_update["suspended_for_hitl"]

                next_node = hitl_gatekeeper_routing(state)
                if next_node == "commit_chained_audit_ledger_node":
                    ledger_update = commit_chained_audit_ledger_node(state)
                    state["execution_permitted"] = ledger_update["execution_permitted"]
                    state["audit_committed"] = ledger_update["audit_committed"]
                    state["audit_record_hash"] = ledger_update["audit_record_hash"]
                    if "audit_ledger" in ledger_update:
                        state["audit_ledger"] = (
                            list(state.get("audit_ledger", []))
                            + ledger_update["audit_ledger"]
                        )

                # Remove the suspended state file from disk upon successful resumption (TRD-5.2)
                if state_file.exists():
                    try:
                        state_file.unlink()
                    except OSError:
                        pass

                return state
        except Timeout as err:
            raise RuntimeError(
                f"Resume lock acquisition timed out for proposal '{proposal_id}'"
            ) from err

    def verify_audit_ledger(self) -> tuple[bool, str]:
        """Verify cryptographic integrity of the audit ledger."""
        return verify_ledger_chain()
