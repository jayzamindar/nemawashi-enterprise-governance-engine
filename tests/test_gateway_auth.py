"""Tests for Mandatory HMAC-SHA256 Gateway Callback Authentication (TRD-5.2)."""

import concurrent.futures
import json
import time
import uuid
from types import SimpleNamespace

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
from nemawashi.main import (
    app,
    compute_resume_signature,
    validate_production_secrets,
)

TEST_SECRET = "nemawashi-enterprise-webhook-secret-32-bytes"


def _fresh_timestamps(ttl_seconds: float = 120.0) -> tuple[float, float, str]:
    now = time.time()
    return now, now + ttl_seconds, str(uuid.uuid4())


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
    issued_at, expires_at, nonce = _fresh_timestamps()
    payload = {
        "proposal_id": hitl_environment["proposal_id"],
        "approved": True,
        "rationale": "Missing signature attempt",
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce": nonce,
    }
    response = client.post("/resume", json=payload)
    assert response.status_code == 401
    assert "Missing HMAC-SHA256 callback signature" in response.json()["detail"]


def test_gateway_unset_webhook_secret_returns_500(
    client, hitl_environment, monkeypatch
):
    """Verify fail-closed architecture when NEMAWASHI_WEBHOOK_SECRET is unset in runtime."""
    monkeypatch.delenv("NEMAWASHI_WEBHOOK_SECRET", raising=False)
    issued_at, expires_at, nonce = _fresh_timestamps()
    payload = {
        "proposal_id": hitl_environment["proposal_id"],
        "approved": True,
        "rationale": "Attempt with missing server secret",
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce": nonce,
        "auth_token": "some-token",
    }
    response = client.post("/resume", json=payload)
    assert response.status_code == 500
    assert "NEMAWASHI_WEBHOOK_SECRET not configured" in response.json()["detail"]


def test_gateway_invalid_signature_returns_401_and_preserves_state(
    client, hitl_environment
):
    """Verify that tampered/invalid signature returns 401 and does NOT mutate or resume state."""
    issued_at, expires_at, nonce = _fresh_timestamps()
    payload = {
        "proposal_id": hitl_environment["proposal_id"],
        "approved": True,
        "rationale": "Tampered signature attempt",
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce": nonce,
    }
    headers = {
        "X-Nemawashi-Signature": "sha256=deadbeefcafebabebadhex00112233445566778899aabbccddeeff"
    }
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
    issued_at, expires_at, nonce = _fresh_timestamps()
    valid_sig = compute_resume_signature(
        proposal_id=hitl_environment["proposal_id"],
        approved=True,
        rationale=rationale,
        secret=TEST_SECRET,
        issued_at=issued_at,
        expires_at=expires_at,
        nonce=nonce,
    )

    payload = {
        "proposal_id": hitl_environment["proposal_id"],
        "approved": True,
        "rationale": rationale,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce": nonce,
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
    issued_at, expires_at, nonce = _fresh_timestamps()
    valid_sig = compute_resume_signature(
        proposal_id=hitl_environment["proposal_id"],
        approved=True,
        rationale=rationale,
        secret=TEST_SECRET,
        issued_at=issued_at,
        expires_at=expires_at,
        nonce=nonce,
    )

    payload = {
        "proposal_id": hitl_environment["proposal_id"],
        "approved": True,
        "rationale": rationale,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce": nonce,
        "auth_token": valid_sig,
    }

    response = client.post("/resume", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "RESUMED"
    assert response.json()["execution_permitted"] is True
    assert not hitl_environment["state_file"].exists()


def test_gateway_malformed_signature_headers_return_401(client, hitl_environment):
    """Verify that malformed signature prefixes, non-hex strings, and truncated hashes are rejected with 401."""
    issued_at, expires_at, nonce = _fresh_timestamps()
    payload = {
        "proposal_id": hitl_environment["proposal_id"],
        "approved": True,
        "rationale": "Adversarial signature header tests",
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce": nonce,
    }

    malformed_headers = [
        "sha1=a9993e364706816aba3e25717850c26c9cd0d89d",
        "md5=098f6bcd4621d373cade4e832627b4f6",
        "sha256=truncated1234",
        "sha256=not_a_valid_hex_string_xyz_zzzzz_00000000000000000000000000000000",
        "bare_hex_without_sha256_prefix",
    ]

    for header in malformed_headers:
        response = client.post(
            "/resume", json=payload, headers={"X-Nemawashi-Signature": header}
        )
        assert response.status_code == 401
        assert "Invalid HMAC-SHA256 callback signature" in response.json()["detail"]


def test_gateway_path_traversal_proposal_id_rejected(client):
    """Verify that path traversal in proposal_id is rejected by schema validation or handler."""
    issued_at, expires_at, nonce = _fresh_timestamps()
    payload = {
        "proposal_id": "../../etc/passwd",
        "approved": True,
        "rationale": "Path traversal attempt",
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce": nonce,
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

    # AgentProposal model boundary rejects path traversal proposal_id
    with pytest.raises(ValueError):
        AgentProposal(
            proposal_id="../evil_path",
            proposing_agent="agent-attacker",
            action_type="escalate",
            action_description="path traversal exploit",
            target_resource="secrets",
        )

    # Defense-in-depth: save_suspended_state also rejects raw object path traversal
    with pytest.raises(ValueError, match="Invalid proposal_id"):
        save_suspended_state({"proposal": SimpleNamespace(proposal_id="../evil_path")})

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
        BaseGovernanceAgent(
            stakeholder_id="adversarial", prompt_file="../../secret.txt"
        )


def test_load_suspended_state_missing_hmac_fails_closed(hitl_environment):
    """Verify load_suspended_state raises ValueError when secret is set and _state_hmac is stripped."""
    state_file = hitl_environment["state_file"]
    with open(state_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "_state_hmac" in data
    del data["_state_hmac"]
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    with pytest.raises(
        ValueError,
        match="Suspended state integrity violation: missing _state_hmac",
    ):
        load_suspended_state(hitl_environment["proposal_id"])


def test_gateway_expired_token_returns_401(client, hitl_environment):
    """Verify /resume rejects expired payloads (current_time >= expires_at) with 401."""
    now = time.time()
    issued_at = now - 120.0
    expires_at = now - 1.0
    nonce = str(uuid.uuid4())
    rationale = "Expired callback attempt"
    sig = compute_resume_signature(
        proposal_id=hitl_environment["proposal_id"],
        approved=True,
        rationale=rationale,
        secret=TEST_SECRET,
        issued_at=issued_at,
        expires_at=expires_at,
        nonce=nonce,
    )
    payload = {
        "proposal_id": hitl_environment["proposal_id"],
        "approved": True,
        "rationale": rationale,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce": nonce,
        "auth_token": sig,
    }
    response = client.post("/resume", json=payload)
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()
    assert hitl_environment["state_file"].exists()


def test_gateway_invalid_ttl_returns_401(client, hitl_environment):
    """Verify /resume rejects TTL > 300s or expires_at <= issued_at with 401."""
    now = time.time()
    issued_at = now
    expires_at = now + 301.0
    nonce = str(uuid.uuid4())
    rationale = "Excessive TTL callback attempt"
    sig = compute_resume_signature(
        proposal_id=hitl_environment["proposal_id"],
        approved=True,
        rationale=rationale,
        secret=TEST_SECRET,
        issued_at=issued_at,
        expires_at=expires_at,
        nonce=nonce,
    )
    payload = {
        "proposal_id": hitl_environment["proposal_id"],
        "approved": True,
        "rationale": rationale,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce": nonce,
        "auth_token": sig,
    }
    response = client.post("/resume", json=payload)
    assert response.status_code == 401
    assert "TTL" in response.json()["detail"]


def test_gateway_replayed_nonce_returns_401(client, hitl_environment):
    """Verify /resume rejects replayed payloads reusing the same nonce with 401."""
    issued_at, expires_at, nonce = _fresh_timestamps()
    rationale = "Approved once; second attempt must be rejected as replay"
    sig = compute_resume_signature(
        proposal_id=hitl_environment["proposal_id"],
        approved=True,
        rationale=rationale,
        secret=TEST_SECRET,
        issued_at=issued_at,
        expires_at=expires_at,
        nonce=nonce,
    )
    payload = {
        "proposal_id": hitl_environment["proposal_id"],
        "approved": True,
        "rationale": rationale,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce": nonce,
        "auth_token": sig,
    }
    first = client.post("/resume", json=payload)
    assert first.status_code == 200

    replay = client.post("/resume", json=payload)
    assert replay.status_code == 401
    assert "Replay detected" in replay.json()["detail"]


def test_gateway_canonical_json_prevents_delimiter_injection(client, hitl_environment):
    """Verify canonical JSON prevents colon delimiter ambiguity and preserves Unicode."""
    issued_at, expires_at, nonce = _fresh_timestamps()
    rationale = "VP approved: region=eu-west-1, café-tier"
    sig_actual = compute_resume_signature(
        proposal_id=hitl_environment["proposal_id"],
        approved=True,
        rationale=rationale,
        secret=TEST_SECRET,
        issued_at=issued_at,
        expires_at=expires_at,
        nonce=nonce,
    )
    sig_ambiguous = compute_resume_signature(
        proposal_id=f"{hitl_environment['proposal_id']}:true",
        approved=False,
        rationale=rationale,
        secret=TEST_SECRET,
        issued_at=issued_at,
        expires_at=expires_at,
        nonce=nonce,
    )
    assert sig_actual != sig_ambiguous

    payload = {
        "proposal_id": hitl_environment["proposal_id"],
        "approved": True,
        "rationale": rationale,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce": nonce,
        "auth_token": sig_actual,
    }
    response = client.post("/resume", json=payload)
    assert response.status_code == 200
    assert response.json()["execution_permitted"] is True


def test_gateway_production_startup_rejects_default_or_missing_secret(monkeypatch):
    """Verify production startup fails closed when NEMAWASHI_WEBHOOK_SECRET is unset, empty, or default."""
    monkeypatch.setenv("ENVIRONMENT", "production")

    for bad_secret in [None, "", "change-me-in-production-32-byte-secret"]:
        if bad_secret is None:
            monkeypatch.delenv("NEMAWASHI_WEBHOOK_SECRET", raising=False)
        else:
            monkeypatch.setenv("NEMAWASHI_WEBHOOK_SECRET", bad_secret)

        with pytest.raises(RuntimeError, match="NEMAWASHI_WEBHOOK_SECRET"):
            validate_production_secrets()

        with (
            pytest.raises(RuntimeError, match="NEMAWASHI_WEBHOOK_SECRET"),
            TestClient(app),
        ):
            pass

    monkeypatch.setenv("NEMAWASHI_WEBHOOK_SECRET", TEST_SECRET)
    validate_production_secrets()


def test_concurrent_resume_engine_race_immunity(hitl_environment):
    """Verify per-proposal_id FileLock prevents duplicate ledger commits on concurrent resume_proposal calls."""
    proposal_id = hitl_environment["proposal_id"]
    engine = NemawashiEngine(max_rounds=3)

    def _attempt_resume(idx: int) -> bool:
        result = engine.resume_proposal(
            proposal_id=proposal_id,
            approved=True,
            rationale=f"Concurrent operator approval #{idx}",
        )
        return bool(result.get("audit_committed"))

    successes = 0
    not_found_errors = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(_attempt_resume, i) for i in range(4)]
        for future in futures:
            try:
                if future.result(timeout=10):
                    successes += 1
            except FileNotFoundError:
                not_found_errors += 1

    assert successes == 1
    assert not_found_errors == 3
    assert not hitl_environment["state_file"].exists()

    valid, msg = verify_ledger_chain(hitl_environment["ledger_file"])
    assert valid is True, f"Ledger verification failed: {msg}"
    assert "1 records intact" in msg


def test_concurrent_resume_gateway_race_immunity(client, hitl_environment):
    """Verify concurrent POST /resume callbacks for the same proposal_id commit strictly once."""
    proposal_id = hitl_environment["proposal_id"]

    def _post_resume(idx: int) -> int:
        issued_at, expires_at, nonce = _fresh_timestamps()
        rationale = f"Concurrent gateway approval #{idx}"
        sig = compute_resume_signature(
            proposal_id=proposal_id,
            approved=True,
            rationale=rationale,
            secret=TEST_SECRET,
            issued_at=issued_at,
            expires_at=expires_at,
            nonce=nonce,
        )
        payload = {
            "proposal_id": proposal_id,
            "approved": True,
            "rationale": rationale,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "nonce": nonce,
            "auth_token": sig,
        }
        response = client.post("/resume", json=payload)
        return response.status_code

    statuses: list[int] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(_post_resume, i) for i in range(3)]
        for future in futures:
            statuses.append(future.result(timeout=10))

    assert statuses.count(200) == 1
    assert statuses.count(404) == 2

    valid, msg = verify_ledger_chain(hitl_environment["ledger_file"])
    assert valid is True, f"Ledger verification failed: {msg}"
    assert "1 records intact" in msg


def test_dynamic_env_var_path_overrides(tmp_path, monkeypatch):
    """Verify NEMAWASHI_STATE_DIR, NEMAWASHI_AUDIT_LOG_DIR, and NEMAWASHI_CACHE_DIR resolve dynamically."""
    custom_state_dir = tmp_path / "dyn_state"
    custom_audit_dir = tmp_path / "dyn_audit"
    custom_cache_dir = tmp_path / "dyn_cache"

    monkeypatch.setenv("NEMAWASHI_STATE_DIR", str(custom_state_dir))
    monkeypatch.setenv("NEMAWASHI_AUDIT_LOG_DIR", str(custom_audit_dir))
    monkeypatch.setenv("NEMAWASHI_CACHE_DIR", str(custom_cache_dir))
    monkeypatch.setenv("NEMAWASHI_WEBHOOK_SECRET", TEST_SECRET)

    engine = NemawashiEngine(max_rounds=3)
    proposal = AgentProposal(
        proposal_id="p-dynamic-paths",
        proposing_agent="agent-scaler",
        action_type="provision_gpu_fleet",
        action_description="Provision GPU cluster verifying dynamic env paths",
        target_resource="gpu-fleet",
        estimated_cost_usd=1500.0,
        estimated_blast_radius=85,
    )

    suspended_state = engine.evaluate_proposal(proposal)
    assert suspended_state.get("suspended_for_hitl") is True

    expected_state_file = (
        custom_state_dir / "suspended_states" / f"{proposal.proposal_id}.json"
    )
    assert expected_state_file.exists()

    resumed_state = engine.resume_proposal(
        proposal_id=proposal.proposal_id,
        approved=True,
        rationale="Dynamic path override verified",
    )
    assert resumed_state["audit_committed"] is True
    assert resumed_state["execution_permitted"] is True
    assert not expected_state_file.exists()

    expected_ledger_file = custom_audit_dir / "nemawashi_ledger.jsonl"
    assert expected_ledger_file.exists()
    valid, msg = verify_ledger_chain()
    assert valid is True, f"Ledger verification failed: {msg}"
    assert "1 records intact" in msg

    expected_cache_file = custom_cache_dir / "semantic_cache.json"
    assert expected_cache_file.exists()


def test_gateway_ready_and_singleton_engine(client):
    """Verify /ready probe returns 200 and get_engine() reuses a singleton instance."""
    from nemawashi.main import get_engine

    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"
    assert get_engine() is get_engine()


def test_gateway_rejects_oversized_content_length_with_413(client):
    """Verify fast-path Content-Length > 10MB returns HTTP 413 Payload Too Large."""
    from nemawashi.main import MAX_REQUEST_BODY_BYTES

    oversized_body = b"{" + (b"a" * MAX_REQUEST_BODY_BYTES) + b"}"
    response = client.post(
        "/resume",
        content=oversized_body,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert "exceeds maximum allowed size" in response.json()["detail"]


def test_gateway_rejects_streaming_chunk_over_10mb_with_413(client):
    """Verify streaming chunked body without Content-Length > 10MB returns HTTP 413."""
    from nemawashi.main import MAX_REQUEST_BODY_BYTES

    def _chunk_stream():
        chunk = b"x" * (1024 * 1024)
        for _ in range((MAX_REQUEST_BODY_BYTES // len(chunk)) + 1):
            yield chunk

    response = client.post(
        "/resume",
        content=_chunk_stream(),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert "exceeds maximum allowed size" in response.json()["detail"]


def test_agent_proposal_rejects_oversized_strings_and_parameters():
    """Verify AgentProposal bounds string lengths and serialized parameters byte ceiling."""
    from pydantic import ValidationError

    from nemawashi.core.models import MAX_PROPOSAL_PARAMETERS_BYTES

    with pytest.raises(ValidationError):
        AgentProposal(
            proposal_id="p-long-desc",
            proposing_agent="agent-1",
            action_type="scale_up",
            action_description="a" * 4097,
            target_resource="pool-1",
        )

    with pytest.raises(ValidationError):
        AgentProposal(
            proposal_id="p-long-agent",
            proposing_agent="a" * 257,
            action_type="scale_up",
            action_description="Scale up",
            target_resource="pool-1",
        )

    with pytest.raises(ValidationError):
        AgentProposal(
            proposal_id="p-long-target",
            proposing_agent="agent-1",
            action_type="scale_up",
            action_description="Scale up",
            target_resource="r" * 513,
        )

    with pytest.raises(ValidationError, match="Serialized parameters exceed"):
        AgentProposal(
            proposal_id="p-huge-params",
            proposing_agent="agent-1",
            action_type="scale_up",
            action_description="Scale up",
            target_resource="pool-1",
            parameters={"blob": "z" * (MAX_PROPOSAL_PARAMETERS_BYTES + 100)},
        )
