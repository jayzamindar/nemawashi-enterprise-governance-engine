"""Cryptographically Chained SHA-256 Audit Ledger.

Enforces an immutable audit chronology by acting as a strict terminal node
in the LangGraph engine topology immediately preceding END. Once a record
enters the ledger block, the state cannot be mutated by human input or downstream
agent iterations.
"""

import hashlib
import json
import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from filelock import FileLock, Timeout

from nemawashi.core.cache import SemanticProposalCache
from nemawashi.core.models import (
    AuditRecord,
    HumanApprovalRecord,
    StructuredAgentVote,
)
from nemawashi.core.state import NemawashiState

logger = logging.getLogger(__name__)

_DEFAULT_LEDGER_PATH = Path("audit_logs") / "nemawashi_ledger.jsonl"
DEFAULT_LEDGER_PATH = _DEFAULT_LEDGER_PATH
GENESIS_HASH = "0" * 64
DEFAULT_AUDIT_LOG_MAX_SIZE_MB = 500
DEFAULT_AUDIT_LOG_MAX_RETENTION_DAYS = 30


def get_audit_log_max_size_bytes() -> int:
    """Resolve max ledger file size in bytes from AUDIT_LOG_MAX_SIZE_MB (default 500MB)."""
    raw = os.getenv("AUDIT_LOG_MAX_SIZE_MB", str(DEFAULT_AUDIT_LOG_MAX_SIZE_MB))
    try:
        mb = float(raw)
    except ValueError:
        mb = float(DEFAULT_AUDIT_LOG_MAX_SIZE_MB)
    if mb <= 0:
        return 0
    return max(1, int(mb * 1024 * 1024))


def get_audit_log_max_retention_days() -> int:
    """Resolve max rotated ledger retention in days from AUDIT_LOG_MAX_RETENTION_DAYS (default 30)."""
    raw = os.getenv(
        "AUDIT_LOG_MAX_RETENTION_DAYS", str(DEFAULT_AUDIT_LOG_MAX_RETENTION_DAYS)
    )
    try:
        days = int(raw)
    except ValueError:
        days = DEFAULT_AUDIT_LOG_MAX_RETENTION_DAYS
    return max(0, days)


def _prune_expired_rotated_ledgers(
    target_path: Path, max_retention_days: int
) -> list[Path]:
    """Delete rotated ledger archive files older than max_retention_days."""
    if max_retention_days <= 0 or not target_path.parent.exists():
        return []
    cutoff_epoch = time.time() - (max_retention_days * 86400)
    pattern = f"{target_path.stem}.*{target_path.suffix}"
    pruned: list[Path] = []
    for candidate in target_path.parent.glob(pattern):
        if candidate.name == target_path.name or not candidate.is_file():
            continue
        try:
            if candidate.stat().st_mtime < cutoff_epoch:
                candidate.unlink(missing_ok=True)
                pruned.append(candidate)
        except OSError as exc:
            logger.warning("Failed to prune rotated ledger %s: %s", candidate, exc)
    return pruned


def rotate_ledger_if_needed(
    target_path: Path,
    max_size_bytes: int | None = None,
    max_retention_days: int | None = None,
) -> Path | None:
    """Rotate active JSONL ledger when size >= max_size_bytes and prune expired archives."""
    size_limit = (
        get_audit_log_max_size_bytes() if max_size_bytes is None else max_size_bytes
    )
    retention_days = (
        get_audit_log_max_retention_days()
        if max_retention_days is None
        else max_retention_days
    )

    rotated_path: Path | None = None
    if size_limit > 0 and target_path.exists():
        try:
            if target_path.stat().st_size >= size_limit:
                ts_slug = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
                rotated_path = target_path.with_name(
                    f"{target_path.stem}.{ts_slug}{target_path.suffix}"
                )
                target_path.replace(rotated_path)
        except OSError as exc:
            logger.warning("Failed to rotate ledger %s: %s", target_path, exc)

    _prune_expired_rotated_ledgers(target_path, retention_days)
    return rotated_path


def get_ledger_path(ledger_path: Path | None = None) -> Path:
    """Resolve audit ledger path dynamically from NEMAWASHI_AUDIT_LOG_DIR or default."""
    if ledger_path is not None:
        return ledger_path
    if DEFAULT_LEDGER_PATH != _DEFAULT_LEDGER_PATH:
        return DEFAULT_LEDGER_PATH
    env_dir = os.getenv("NEMAWASHI_AUDIT_LOG_DIR")
    if env_dir and env_dir.strip():
        return Path(env_dir.strip()) / "nemawashi_ledger.jsonl"
    return DEFAULT_LEDGER_PATH


def _get_dynamic_cache_path() -> Path | None:
    """Resolve semantic cache path dynamically from NEMAWASHI_CACHE_DIR when not monkeypatched."""
    import nemawashi.core.cache as cache_mod

    if cache_mod.DEFAULT_CACHE_PATH.parent.name != "cache":
        return None
    env_dir = os.getenv("NEMAWASHI_CACHE_DIR")
    if env_dir and env_dir.strip():
        return Path(env_dir.strip()) / "semantic_cache.json"
    return None


def canonical_json(obj: Any) -> str:
    """Serialize obj to strict canonical JSON for deterministic hashing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


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
    vote_history_json: str | None = None,
) -> str:
    """Compute deterministic SHA-256 hash for a ledger record block."""
    payload = (
        f"{index}:{previous_hash}:{timestamp}:{proposal_id}:{verdict}:"
        f"{str(execution_permitted).lower()}:{composite_risk_score}:"
        f"{serialized_votes}:{mitigations_json}:{human_approval_json}:{round_num}:{total_cost_usd:.6f}"
    )
    if vote_history_json is not None:
        payload = f"{payload}:{vote_history_json}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_latest_ledger_hash(ledger_path: Path | None = None) -> tuple[int, str]:
    """Retrieve the index and hash of the most recent committed record in the ledger.

    Returns:
        Tuple of (latest_index, latest_hash). If ledger is empty or non-existent,
        returns (-1, GENESIS_HASH).
    """
    path = get_ledger_path(ledger_path)
    if not path.exists():
        return -1, GENESIS_HASH

    last_line = ""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    last_line = stripped
        if not last_line:
            return -1, GENESIS_HASH
        record = json.loads(last_line)
        return int(record.get("index", 0)), str(record.get("record_hash", GENESIS_HASH))
    except (OSError, json.JSONDecodeError, ValueError):
        return -1, GENESIS_HASH


def commit_chained_audit_ledger_node(
    state: NemawashiState,
    ledger_path: Path | None = None,
) -> dict[str, Any]:
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

    target_path = get_ledger_path(ledger_path)
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
        mitigations: list[str] = [
            "WATCHDOG_INTERVENTION: Deliberation loop ceiling exceeded"
        ]
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
    serialized_votes_map: dict[str, dict[str, Any]] = {}
    validated_votes_map: dict[str, StructuredAgentVote] = {}
    for k in sorted(raw_votes.keys()):
        v = raw_votes[k]
        if isinstance(v, StructuredAgentVote):
            serialized_votes_map[k] = v.model_dump()
            validated_votes_map[k] = v
        elif isinstance(v, dict):
            validated_vote = StructuredAgentVote.model_validate(v)
            serialized_votes_map[k] = validated_vote.model_dump()
            validated_votes_map[k] = validated_vote
        else:
            serialized_votes_map[k] = {"raw": str(v)}

    serialized_votes_str = canonical_json(serialized_votes_map)
    mitigations_json = canonical_json(sorted(mitigations))

    # Preserve full chronological multi-round vote lineage from state["votes"]
    raw_vote_history = state.get("votes", [])
    validated_vote_history: list[StructuredAgentVote] = []
    serialized_vote_history: list[dict[str, Any]] = []
    for item in raw_vote_history:
        if isinstance(item, StructuredAgentVote):
            validated_vote_history.append(item)
            serialized_vote_history.append(item.model_dump())
        elif isinstance(item, dict):
            validated_item = StructuredAgentVote.model_validate(item)
            validated_vote_history.append(validated_item)
            serialized_vote_history.append(validated_item.model_dump())
    vote_history_json = (
        canonical_json(serialized_vote_history) if serialized_vote_history else None
    )

    # Human sign-off payload
    human_approval: HumanApprovalRecord | None = None
    if state.get("human_approved") is not None:
        human_approval = HumanApprovalRecord(
            approved=bool(state.get("human_approved")),
            rationale=str(state.get("human_rationale", "")),
        )
    human_approval_json = (
        canonical_json(human_approval.model_dump()) if human_approval else "null"
    )

    # Mutex Locking: acquire cross-platform filelock before rotating, reading parent hash, or writing block
    lock_file = f"{target_path}.lock"
    try:
        with FileLock(lock_file, timeout=10):
            rotate_ledger_if_needed(target_path)
            # Query cryptographic parent hash inside lock
            last_index, previous_hash = get_latest_ledger_hash(target_path)
            new_index = last_index + 1
            timestamp = datetime.now(UTC).isoformat()
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
                vote_history_json=vote_history_json,
            )

            audit_entry = AuditRecord(
                index=new_index,
                timestamp=timestamp,
                proposal_id=proposal.proposal_id,
                action_type=proposal.action_type,
                verdict=verdict,
                execution_permitted=execution_permitted,
                composite_risk_score=composite_risk,
                stakeholder_votes=validated_votes_map,
                vote_history=validated_vote_history,
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
            cache = SemanticProposalCache(cache_path=_get_dynamic_cache_path())
            cache.store(
                proposal=proposal,
                resolution=resolution,
                stakeholder_votes=state.get("stakeholder_votes", {}),
                deliberation_round=state.get("current_round", 1),
            )
        except Exception as err:  # noqa: BLE001
            logger.warning("Failed to store proposal in semantic cache: %s", err)

    # Return state update marking the state as permanently committed and immutable
    return {
        "execution_permitted": execution_permitted,
        "audit_committed": True,
        "audit_record_hash": record_hash,
        "audit_ledger": [audit_entry.model_dump()],
    }


def verify_ledger_chain(ledger_path: Path | None = None) -> tuple[bool, str]:
    """Verify cryptographic integrity of the entire SHA-256 JSONL audit ledger.

    Returns:
        (True, "OK") if all hashes and chain links are mathematically valid.
        (False, error_description) if any corruption, deletion, or tampering occurred.
    """
    path = get_ledger_path(ledger_path)
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
                    except json.JSONDecodeError as e:
                        return False, f"Line {line_num}: Invalid JSON syntax ({e})"

                    idx = record.get("index")
                    prev_hash = record.get("previous_hash")
                    rec_hash = record.get("record_hash")

                    if idx != expected_index:
                        return (
                            False,
                            f"Line {line_num}: Index mismatch (expected {expected_index}, got {idx})",
                        )

                    if prev_hash != expected_prev_hash:
                        return False, (
                            f"Line {line_num}: Chain broken! Previous hash mismatch.\n"
                            f"  Expected: {expected_prev_hash}\n"
                            f"  Got:      {prev_hash}"
                        )

                    # Recompute hash
                    human_approval = record.get("human_approval")
                    human_approval_json = (
                        canonical_json(human_approval) if human_approval else "null"
                    )
                    votes_json = canonical_json(record.get("stakeholder_votes", {}))
                    mitigations_json = canonical_json(
                        sorted(record.get("mitigations", []))
                    )
                    cost = float(record.get("total_cost_usd", 0.0))
                    raw_vote_history = record.get("vote_history") or []
                    vote_history_json = (
                        canonical_json(raw_vote_history) if raw_vote_history else None
                    )

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
                        vote_history_json=vote_history_json,
                    )

                    if recomputed != rec_hash:
                        return False, (
                            f"Line {line_num}: Tamper detected! Hash mismatch for record {idx}.\n"
                            f"  Stored:     {rec_hash}\n"
                            f"  Recomputed: {recomputed}"
                        )

                    expected_prev_hash = rec_hash
                    expected_index += 1

            return (
                True,
                f"Ledger verified successfully ({expected_index} records intact).",
            )
    except Timeout as err:
        raise RuntimeError("Audit ledger lock acquisition timed out") from err
