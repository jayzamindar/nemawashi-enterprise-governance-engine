"""Tests for Mandatory HMAC-SHA256 Gateway Callback Authentication (TRD-5.2)."""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from nemawashi.agents.base import BaseGovernanceAgent
from nemawashi.audit.ledger import verify_ledger_chain
from nemawashi.core.engine import NemawashiEngine
from nemawashi.core.graph import (
    load_suspended_state,
    save_suspended_state,
    validate_proposal_id,
)
from nemawashi.core.models import AgentProposal
from nemawashi.main import app, compute_resume_signature

TEST_SECRET = "nemawashi-enterprise-webhook-secret-32-bytes"


@pytest.fixture
def client():
    """Context-managed FastAPI TestClient avoiding hanging threads or nested loops."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def hitl_environment(tmp_path, monkeypatch):
    """Setup isolated ledger and storage environment with configured webhook secret."""
    audit_dir = tmp_path / "audit_logs"
    cache_dir = tmp_path / "cache"
    storage_dir = tmp_path / "storage" / "suspended_states"
    ledger_file = audit_dir / "nemawashi_ledger.jsonl"

    audit_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    storage_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("NEMAWASHI_AUDIT_LOG_DIR", str(audit_dir))
    monkeypatch.setenv("NEMAWASHI_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("NEMAWASHI_STATE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("NEMAWASHI_WEBHOOK_SECRET", TEST_SECRET)

    monkeypatch.setattr("nemawashi.audit.ledger.DEFAULT_LEDGER_PATH", ledger_file)
    monkeypatch.setattr("nemawashi.core.graph.SUSPENDED_STATES_DIR", storage_dir)

    engine = NemawashiEngine(max_rounds=3)
    proposal = AgentProposal(
        proposal_id="p-hitl-gate",
        proposing_agent="agent-scaler",
        action_type="provision_gpu_fleet",
        action_description="Provision GPU cluster requiring human sign-off",
        target_resource="gpu-fleet",
        estimated_cost_usd=1500.0,
        estimated_blast_radius=85,
    )

    # Suspend proposal awaiting operator callback
    suspended_state = engine.evaluate_proposal(proposal)
    assert suspended_state.get("suspended_for_hitl") is True

    state_file = storage_dir / f"{proposal.proposal_id}.json"
    assert state_file.exists()

    return {
        "proposal_id": proposal.proposal_id,
        "ledger_file": ledger_file,
        "storage_dir": storage_dir,
        "state_file": state_file,
    }


def test_gateway_missing_signature_returns_401(client, hitl_environment):
    """Verify that requests missing both X-Nemawashi-Signature and auth_token return 401."""
    payload = {
        "proposal_id": hitl_environment["proposal_id"],
        "approved": True,
        "rationale": "Missing signature attempt",
    }
    response = client.post("/resume", json=payload)
    assert response.status_code == 401
    assert "Missing HMAC-SHA256 callback signature" in response.json()["detail"]


def test_gateway_unset_webhook_secret_returns_500(client, hitl_environment, monkeypatch):
    """Verify fail-closed architecture when NEMAWASHI_WEBHOOK_SECRET is unset in runtime."""
    monkeypatch.delenv("NEMAWASHI_WEBHOOK_SECRET", raising=False)
    payload = {
        "proposal_id": hitl_environment["proposal_id"],
        "approved": True,
        "rationale": "Attempt with missing server secret",
        "auth_token": "some-token",
    }
    response = client.post("/resume", json=payload)
    assert response.status_code == 500
    assert "NEMAWASHI_WEBHOOK_SECRET not configured" in response.json()["detail"]


def test_gateway_invalid_signature_returns_401_and_preserves_state(client, hitl_environment):
    """Verify that tampered/invalid signature returns 401 and does NOT mutate or resume state."""
    payload = {
        "proposal_id": hitl_environment["proposal_id"],
        "approved": True,
        "rationale": "Tampered signature attempt",
    }
    headers = {"X-Nemawashi-Signature": "sha256=deadbeefcafebabebadhex00112233445566778899aabbccddeeff"}
    response = client.post("/resume", json=payload, headers=headers)
    assert response.status_code == 401
    assert "Invalid HMAC-SHA256 callback signature" in response.json()["detail"]

    # State file must remain suspended on disk
    assert hitl_environment["state_file"].exists()

    # Ledger must not have committed any resumption record
    assert not hitl_environment["ledger_file"].exists()


def test_gateway_valid_signature_header_resumes_and_commits(client, hitl_environment):
    """Verify that valid HMAC header unfreezes state, authorizes execution, and seals ledger."""
    rationale = "Executive VP authorized deployment after security review"
    valid_sig = compute_resume_signature(
        proposal_id=hitl_environment["proposal_id"],
        approved=True,
        rationale=rationale,
        secret=TEST_SECRET,
    )

    payload = {
        "proposal_id": hitl_environment["proposal_id"],
        "approved": True,
        "rationale": rationale,
    }
    headers = {"X-Nemawashi-Signature": f"sha256={valid_sig}"}

    response = client.post("/resume", json=payload, headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "RESUMED"
    assert data["proposal_id"] == hitl_environment["proposal_id"]
    assert data["execution_permitted"] is True
    assert data["human_approved"] is True
    assert data["verdict"] == "HUMAN_IN_THE_LOOP_ESCALATION"
    assert data["audit_committed"] is True
    assert data["audit_record_hash"] is not None

    # Suspended state file must be cleaned up
    assert not hitl_environment["state_file"].exists()

    # Chained ledger must verify with 100% integrity
    assert hitl_environment["ledger_file"].exists()
    valid, msg = verify_ledger_chain(hitl_environment["ledger_file"])
    assert valid is True, f"Ledger verification failed: {msg}"
    assert "1 records intact" in msg


def test_gateway_valid_auth_token_in_body_resumes_and_commits(client, hitl_environment):
    """Verify that signature passed via auth_token in request body succeeds as valid fallback."""
    rationale = "Lead SRE approved cluster scaling via webhook body token"
    valid_sig = compute_resume_signature(
        proposal_id=hitl_environment["proposal_id"],
        approved=True,
        rationale=rationale,
        secret=TEST_SECRET,
    )

    payload = {
        "proposal_id": hitl_environment["proposal_id"],
        "approved": True,
        "rationale": rationale,
        "auth_token": valid_sig,
    }

    response = client.post("/resume", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "RESUMED"
    assert response.json()["execution_permitted"] is True
    assert not hitl_environment["state_file"].exists()


def test_gateway_malformed_signature_headers_return_401(client, hitl_environment):
    """Verify that malformed signature prefixes, non-hex strings, and truncated hashes are rejected with 401."""
    payload = {
        "proposal_id": hitl_environment["proposal_id"],
        "approved": True,
        "rationale": "Adversarial signature header tests",
    }

    malformed_headers = [
        "sha1=a9993e364706816aba3e25717850c26c9cd0d89d",
        "md5=098f6bcd4621d373cade4e832627b4f6",
        "sha256=truncated1234",
        "sha256=not_a_valid_hex_string_xyz_zzzzz_00000000000000000000000000000000",
        "bare_hex_without_sha256_prefix",
    ]

    for header in malformed_headers:
        response = client.post("/resume", json=payload, headers={"X-Nemawashi-Signature": header})
        assert response.status_code == 401
        assert "Invalid HMAC-SHA256 callback signature" in response.json()["detail"]


def test_gateway_path_traversal_proposal_id_rejected(client):
    """Verify that path traversal in proposal_id is rejected by schema validation or handler."""
    payload = {
        "proposal_id": "../../etc/passwd",
        "approved": True,
        "rationale": "Path traversal attempt",
        "auth_token": "dummy",
    }
    response = client.post("/resume", json=payload)
    # Pydantic regex pattern validation rejects invalid ID format with HTTP 422
    assert response.status_code in (400, 422)


def test_suspended_state_path_traversal_and_hmac_tampering(hitl_environment):
    """Verify path traversal prevention and HMAC tampering rejection in state storage."""
    # 1. Path traversal attempts raise ValueError
    with pytest.raises(ValueError, match="Invalid proposal_id"):
        validate_proposal_id("../evil_path")

    malicious_proposal = AgentProposal(
        proposal_id="../evil_path",
        proposing_agent="agent-attacker",
        action_type="escalate",
        action_description="path traversal exploit",
        target_resource="secrets",
    )
    with pytest.raises(ValueError, match="Invalid proposal_id"):
        save_suspended_state({"proposal": malicious_proposal})

    with pytest.raises(ValueError, match="Invalid proposal_id"):
        load_suspended_state("../evil_path")

    # 2. State file HMAC tampering detection
    state_file = hitl_environment["state_file"]
    assert state_file.exists()

    with open(state_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "_state_hmac" in data

    # Tamper with proposal data without updating HMAC
    data["proposal"]["estimated_cost_usd"] = 999999.0
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    with pytest.raises(
        ValueError,
        match="Suspended state integrity violation: HMAC mismatch",
    ):
        load_suspended_state(hitl_environment["proposal_id"])


def test_prompt_traversal_guard():
    """Verify BaseGovernanceAgent blocks directory traversal in prompt file paths."""
    with pytest.raises(ValueError, match="Path traversal detected"):
        BaseGovernanceAgent(stakeholder_id="adversarial", prompt_file="../../secret.txt")

