"""Tests for Cryptographically Chained SHA-256 Audit Ledger and Immutability Guarantees."""

import json
from pathlib import Path
import pytest

from nemawashi.audit.ledger import (
    GENESIS_HASH,
    commit_chained_audit_ledger_node,
    verify_ledger_chain,
)
from nemawashi.core.models import AgentProposal, Resolution, StructuredAgentVote
from nemawashi.core.state import create_initial_state


def test_genesis_record_and_chaining(tmp_path):
    """Verify that the first record chains to GENESIS_HASH and subsequent records chain to previous record_hash."""
    ledger_file = tmp_path / "test_ledger.jsonl"

    proposal_1 = AgentProposal(
        proposal_id="p-1",
        proposing_agent="agent-1",
        action_type="scale_up",
        action_description="Scale up",
        target_resource="pool-1",
        estimated_cost_usd=10.0,
        estimated_blast_radius=5,
    )
    state_1 = create_initial_state(proposal=proposal_1)
    state_1["policy_passed"] = True
    state_1["resolution"] = Resolution(
        proposal_id="p-1",
        verdict="UNANIMOUS_CONSENSUS",
        composite_risk_score=10,
        summary="Approved",
    )

    # Commit record 1
    res_1 = commit_chained_audit_ledger_node(state_1, ledger_path=ledger_file)
    assert res_1["audit_committed"] is True
    hash_1 = res_1["audit_record_hash"]

    # Commit record 2
    proposal_2 = AgentProposal(
        proposal_id="p-2",
        proposing_agent="agent-2",
        action_type="scale_down",
        action_description="Scale down",
        target_resource="pool-2",
        estimated_cost_usd=0.0,
        estimated_blast_radius=5,
    )
    state_2 = create_initial_state(proposal=proposal_2)
    state_2["policy_passed"] = True
    state_2["resolution"] = Resolution(
        proposal_id="p-2",
        verdict="UNANIMOUS_CONSENSUS",
        composite_risk_score=5,
        summary="Approved",
    )
    res_2 = commit_chained_audit_ledger_node(state_2, ledger_path=ledger_file)
    hash_2 = res_2["audit_record_hash"]

    # Inspect file lines
    with open(ledger_file, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]

    assert len(lines) == 2
    assert lines[0]["index"] == 0
    assert lines[0]["previous_hash"] == GENESIS_HASH
    assert lines[0]["record_hash"] == hash_1

    assert lines[1]["index"] == 1
    assert lines[1]["previous_hash"] == hash_1
    assert lines[1]["record_hash"] == hash_2

    # Verify cryptographic integrity
    valid, msg = verify_ledger_chain(ledger_file)
    assert valid is True
    assert "2 records intact" in msg


def test_token_and_cost_accounting_in_audit_record(tmp_path):
    """Verify that cumulative token and financial metrics are permanently preserved in the ledger."""
    ledger_file = tmp_path / "tokens_ledger.jsonl"

    proposal = AgentProposal(
        proposal_id="p-tok",
        proposing_agent="agent-worker",
        action_type="scale",
        action_description="scale",
        target_resource="target",
    )
    state = create_initial_state(proposal=proposal)
    state["policy_passed"] = True
    state["prompt_tokens"] = 1200
    state["completion_tokens"] = 350
    state["total_cost_usd"] = 0.000195
    state["resolution"] = Resolution(
        proposal_id="p-tok",
        verdict="UNANIMOUS_CONSENSUS",
        composite_risk_score=15,
        summary="Approved with tokens",
    )

    commit_chained_audit_ledger_node(state, ledger_path=ledger_file)

    with open(ledger_file, "r", encoding="utf-8") as f:
        record = json.loads(f.readline())

    assert record["prompt_tokens"] == 1200
    assert record["completion_tokens"] == 350
    assert record["total_cost_usd"] == 0.000195

    valid, msg = verify_ledger_chain(ledger_file)
    assert valid is True


def test_tamper_detection(tmp_path):
    """Verify that modifying any byte in the ledger file causes cryptographic verification to fail."""
    ledger_file = tmp_path / "tamper_ledger.jsonl"

    proposal = AgentProposal(
        proposal_id="p-tamper",
        proposing_agent="agent-1",
        action_type="scale_up",
        action_description="Scale up",
        target_resource="pool-1",
    )
    state = create_initial_state(proposal=proposal)
    state["policy_passed"] = True
    state["resolution"] = Resolution(
        proposal_id="p-tamper",
        verdict="UNANIMOUS_CONSENSUS",
        composite_risk_score=10,
        summary="Approved",
    )

    commit_chained_audit_ledger_node(state, ledger_path=ledger_file)

    # Read and maliciously modify record
    with open(ledger_file, "r", encoding="utf-8") as f:
        record = json.loads(f.readline())

    record["composite_risk_score"] = 99  # Tampering

    with open(ledger_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    valid, msg = verify_ledger_chain(ledger_file)
    assert valid is False
    assert "Tamper detected!" in msg


def test_state_immutability_assertion(tmp_path):
    """Verify FIX HOLE 3: Once a state is committed, calling the ledger node again raises RuntimeError."""
    ledger_file = tmp_path / "immutable_test.jsonl"

    proposal = AgentProposal(
        proposal_id="p-imm",
        proposing_agent="agent-1",
        action_type="deploy",
        action_description="Deploy",
        target_resource="res-1",
    )
    state = create_initial_state(proposal=proposal)
    state["policy_passed"] = True
    state["resolution"] = Resolution(
        proposal_id="p-imm",
        verdict="UNANIMOUS_CONSENSUS",
        composite_risk_score=10,
        summary="Approved",
    )

    # First commitment succeeds
    res = commit_chained_audit_ledger_node(state, ledger_path=ledger_file)
    state.update(res)

    # Subsequent mutation attempt must fail
    with pytest.raises(RuntimeError) as exc_info:
        commit_chained_audit_ledger_node(state, ledger_path=ledger_file)

    assert "State immutability violation" in str(exc_info.value)


def test_concurrent_ledger_commits_maintain_unbroken_hash_chain(tmp_path):
    """Verify that multiple concurrent threads committing to the ledger maintain a sequential unbroken hash chain."""
    import concurrent.futures

    ledger_file = tmp_path / "concurrent_ledger.jsonl"
    num_threads = 10

    def commit_record(i: int):
        proposal = AgentProposal(
            proposal_id=f"p-concurrent-{i}",
            proposing_agent=f"agent-{i}",
            action_type="scale_cluster",
            action_description=f"Concurrent scale action {i}",
            target_resource=f"resource-{i}",
            estimated_cost_usd=float(i),
            estimated_blast_radius=5,
        )
        state = create_initial_state(proposal=proposal)
        state["policy_passed"] = True
        state["resolution"] = Resolution(
            proposal_id=f"p-concurrent-{i}",
            verdict="UNANIMOUS_CONSENSUS",
            composite_risk_score=5,
            summary=f"Approved concurrent task {i}",
        )
        return commit_chained_audit_ledger_node(state, ledger_path=ledger_file)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(commit_record, i) for i in range(num_threads)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == num_threads
    for res in results:
        assert res["audit_committed"] is True
        assert res["audit_record_hash"] is not None

    # Verify that all 10 records are written sequentially (indices 0 through 9)
    with open(ledger_file, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    assert len(records) == num_threads
    indices = [r["index"] for r in records]
    assert indices == list(range(num_threads)), f"Indices must appear in sequential order 0..{num_threads-1}, got: {indices}"

    # Verify cryptographic integrity of the entire chain
    valid, msg = verify_ledger_chain(ledger_file)
    assert valid is True, f"Ledger verification failed: {msg}"
    assert f"{num_threads} records intact" in msg


def test_ledger_lock_timeout_raises_runtime_error(tmp_path, monkeypatch):
    """Verify that filelock.Timeout is caught and converted to a clean RuntimeError (TRD-3.2)."""
    from filelock import FileLock, Timeout

    ledger_file = tmp_path / "timeout_ledger.jsonl"
    ledger_file.touch()

    proposal = AgentProposal(
        proposal_id="p-timeout",
        proposing_agent="agent-worker",
        action_type="scale",
        action_description="scale",
        target_resource="target",
    )
    state = create_initial_state(proposal=proposal)
    state["policy_passed"] = True
    state["resolution"] = Resolution(
        proposal_id="p-timeout",
        verdict="UNANIMOUS_CONSENSUS",
        composite_risk_score=5,
        summary="Approved",
    )

    def mock_enter(self):
        raise Timeout("Simulated lock timeout")

    monkeypatch.setattr(FileLock, "__enter__", mock_enter)

    with pytest.raises(RuntimeError, match="Audit ledger lock acquisition timed out"):
        commit_chained_audit_ledger_node(state, ledger_path=ledger_file)

    with pytest.raises(RuntimeError, match="Audit ledger lock acquisition timed out"):
        verify_ledger_chain(ledger_path=ledger_file)

