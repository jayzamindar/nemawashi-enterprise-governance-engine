"""Cryptographically Chained SHA-256 Audit Ledger.

Enforces an immutable audit chronology by acting as a strict terminal node
in the LangGraph engine topology immediately preceding END. Once a record
enters the ledger block, the state cannot be mutated by human input or downstream
agent iterations.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from filelock import FileLock, Timeout

from nemawashi.core.cache import SemanticProposalCache
from nemawashi.core.models import AuditRecord, StructuredAgentVote
from nemawashi.core.state import NemawashiState

DEFAULT_LEDGER_PATH = Path("audit_logs") / "nemawashi_ledger.jsonl"
GENESIS_HASH = "0" * 64


def calculate_record_hash(
    index: int,
    previous_hash: str,
    timestamp: str,
    proposal_id: str,
    verdict: str,
    execution_permitted: bool,
    composite_risk_score: int,
    serialized_votes: str,
    mitigations_json: str,
    human_approval_json: str,
    round_num: int,
    total_cost_usd: float = 0.0,
) -> str:
    """Compute deterministic SHA-256 hash for a ledger record block."""
    payload = (
        f"{index}:{previous_hash}:{timestamp}:{proposal_id}:{verdict}:"
        f"{str(execution_permitted).lower()}:{composite_risk_score}:"
        f"{serialized_votes}:{mitigations_json}:{human_approval_json}:{round_num}:{total_cost_usd:.6f}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_latest_ledger_hash(ledger_path: Optional[Path] = None) -> Tuple[int, str]:
    """Retrieve the index and hash of the most recent committed record in the ledger.

    Returns:
        Tuple of (latest_index, latest_hash). If ledger is empty or non-existent,
        returns (-1, GENESIS_HASH).
    """
    path = ledger_path or DEFAULT_LEDGER_PATH
    if not path.exists():
        return -1, GENESIS_HASH

    last_line = ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    last_line = stripped
        if not last_line:
            return -1, GENESIS_HASH
        record = json.loads(last_line)
        return int(record.get("index", 0)), str(record.get("record_hash", GENESIS_HASH))
    except Exception:
        return -1, GENESIS_HASH


def commit_chained_audit_ledger_node(
    state: NemawashiState,
    ledger_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Strict terminal node in LangGraph immediately preceding END.

    Ensures the state cannot be mutated once sealed into the cryptographic chain.
    Atomically writes an immutable AuditRecord to the SHA-256 chained JSONL ledger.

    Raises:
        RuntimeError: If called on a state that has already been committed to the ledger.
    """
    # FIX HOLE 3: Immutability assertion
    if state.get("audit_committed", False):
        raise RuntimeError(
            "State immutability violation: Audit ledger entry has already been sealed. "
            "No downstream or post-hoc mutations are permitted."
        )

    target_path = ledger_path or DEFAULT_LEDGER_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)

    proposal = state["proposal"]
    resolution = state.get("resolution")
    policy_passed = state.get("policy_passed", False)
    policy_violations = state.get("policy_violations", [])
    loop_veto_triggered = state.get("loop_veto_triggered", False)

    # Determine final verdict and execution authority
    if loop_veto_triggered:
        verdict = "CONSENSUS_VETO"
        execution_permitted = False
        composite_risk = 100
        mitigations: list[str] = ["WATCHDOG_INTERVENTION: Deliberation loop ceiling exceeded"]
    elif not policy_passed:
        verdict = "CONSENSUS_VETO"
        execution_permitted = False
        composite_risk = 100
        mitigations = [f"POLICY_VIOLATION: {v}" for v in policy_violations]
    elif resolution is not None:
        verdict = resolution.verdict
        composite_risk = resolution.composite_risk_score
        mitigations = list(resolution.mandatory_mitigations)

        # Check HITL resolution override
        if verdict == "HUMAN_IN_THE_LOOP_ESCALATION":
            execution_permitted = bool(state.get("human_approved", False))
        elif verdict in ("UNANIMOUS_CONSENSUS", "CONDITIONAL_ALIGNMENT"):
            execution_permitted = True
        else:
            execution_permitted = False
    else:
        verdict = "CONSENSUS_VETO"
        execution_permitted = False
        composite_risk = 100
        mitigations = ["UNKNOWN_STATE_HALT"]

    # Normalize serialized structured votes (sorted by key for deterministic hashing)
    raw_votes = state.get("stakeholder_votes", {})
    serialized_votes_map: Dict[str, Dict[str, Any]] = {}
    for k in sorted(raw_votes.keys()):
        v = raw_votes[k]
        if isinstance(v, StructuredAgentVote):
            serialized_votes_map[k] = v.model_dump()
        elif isinstance(v, dict):
            serialized_votes_map[k] = v
        else:
            serialized_votes_map[k] = {"raw": str(v)}

    serialized_votes_str = json.dumps(serialized_votes_map, sort_keys=True)
    mitigations_json = json.dumps(sorted(mitigations))

    # Human sign-off payload
    human_approval = None
    if state.get("human_approved") is not None:
        human_approval = {
            "approved": state.get("human_approved"),
            "rationale": state.get("human_rationale", ""),
        }
    human_approval_json = json.dumps(human_approval, sort_keys=True) if human_approval else "null"

    # Mutex Locking: acquire cross-platform filelock before reading parent hash or writing block
    lock_file = f"{target_path}.lock"
    try:
        with FileLock(lock_file, timeout=10):
            # Query cryptographic parent hash inside lock
            last_index, previous_hash = get_latest_ledger_hash(target_path)
            new_index = last_index + 1
            timestamp = datetime.now(timezone.utc).isoformat()
            deliberation_round = state.get("current_round", 1)
            prompt_tokens = state.get("prompt_tokens", 0)
            completion_tokens = state.get("completion_tokens", 0)
            total_cost_usd = state.get("total_cost_usd", 0.0)

            record_hash = calculate_record_hash(
                index=new_index,
                previous_hash=previous_hash,
                timestamp=timestamp,
                proposal_id=proposal.proposal_id,
                verdict=verdict,
                execution_permitted=execution_permitted,
                composite_risk_score=composite_risk,
                serialized_votes=serialized_votes_str,
                mitigations_json=mitigations_json,
                human_approval_json=human_approval_json,
                round_num=deliberation_round,
                total_cost_usd=total_cost_usd,
            )

            audit_entry = AuditRecord(
                index=new_index,
                timestamp=timestamp,
                proposal_id=proposal.proposal_id,
                action_type=proposal.action_type,
                verdict=verdict,
                execution_permitted=execution_permitted,
                composite_risk_score=composite_risk,
                stakeholder_votes=serialized_votes_map,
                mitigations=mitigations,
                human_approval=human_approval,
                deliberation_round=deliberation_round,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_cost_usd=total_cost_usd,
                cache_hit=bool(state.get("cache_hit", False)),
                previous_hash=previous_hash,
                record_hash=record_hash,
            )

            # Atomically append to ledger JSONL inside lock
            with open(target_path, "a", encoding="utf-8") as f:
                f.write(audit_entry.model_dump_json() + "\n")
    except Timeout as err:
        raise RuntimeError("Audit ledger lock acquisition timed out") from err

    # If not a cache hit and resolution exists, register in semantic cache with vote lineage
    if resolution is not None and not state.get("cache_hit", False):
        try:
            cache = SemanticProposalCache()
            cache.store(
                proposal=proposal,
                resolution=resolution,
                stakeholder_votes=state.get("stakeholder_votes", {}),
                deliberation_round=state.get("current_round", 1),
            )
        except Exception:
            pass

    # Return state update marking the state as permanently committed and immutable
    return {
        "execution_permitted": execution_permitted,
        "audit_committed": True,
        "audit_record_hash": record_hash,
        "audit_ledger": [audit_entry.model_dump()],
    }


def verify_ledger_chain(ledger_path: Optional[Path] = None) -> Tuple[bool, str]:
    """Verify cryptographic integrity of the entire SHA-256 JSONL audit ledger.

    Returns:
        (True, "OK") if all hashes and chain links are mathematically valid.
        (False, error_description) if any corruption, deletion, or tampering occurred.
    """
    path = ledger_path or DEFAULT_LEDGER_PATH
    if not path.exists():
        return True, "Ledger does not exist yet (clean slate)."

    path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = f"{path}.lock"
    try:
        with FileLock(lock_file, timeout=10):
            if not path.exists():
                return True, "Ledger does not exist yet (clean slate)."

            expected_prev_hash = GENESIS_HASH
            expected_index = 0

            with open(path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        record = json.loads(stripped)
                    except Exception as e:
                        return False, f"Line {line_num}: Invalid JSON syntax ({e})"

                    idx = record.get("index")
                    prev_hash = record.get("previous_hash")
                    rec_hash = record.get("record_hash")

                    if idx != expected_index:
                        return False, f"Line {line_num}: Index mismatch (expected {expected_index}, got {idx})"

                    if prev_hash != expected_prev_hash:
                        return False, (
                            f"Line {line_num}: Chain broken! Previous hash mismatch.\n"
                            f"  Expected: {expected_prev_hash}\n"
                            f"  Got:      {prev_hash}"
                        )

                    # Recompute hash
                    human_approval = record.get("human_approval")
                    human_approval_json = json.dumps(human_approval, sort_keys=True) if human_approval else "null"
                    votes_json = json.dumps(record.get("stakeholder_votes", {}), sort_keys=True)
                    mitigations_json = json.dumps(sorted(record.get("mitigations", [])))
                    cost = float(record.get("total_cost_usd", 0.0))

                    recomputed = calculate_record_hash(
                        index=idx,
                        previous_hash=prev_hash,
                        timestamp=record.get("timestamp"),
                        proposal_id=record.get("proposal_id"),
                        verdict=record.get("verdict"),
                        execution_permitted=record.get("execution_permitted"),
                        composite_risk_score=record.get("composite_risk_score"),
                        serialized_votes=votes_json,
                        mitigations_json=mitigations_json,
                        human_approval_json=human_approval_json,
                        round_num=record.get("deliberation_round", 1),
                        total_cost_usd=cost,
                    )

                    if recomputed != rec_hash:
                        return False, (
                            f"Line {line_num}: Tamper detected! Hash mismatch for record {idx}.\n"
                            f"  Stored:     {rec_hash}\n"
                            f"  Recomputed: {recomputed}"
                        )

                    expected_prev_hash = rec_hash
                    expected_index += 1

            return True, f"Ledger verified successfully ({expected_index} records intact)."
    except Timeout as err:
        raise RuntimeError("Audit ledger lock acquisition timed out") from err
