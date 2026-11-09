"""End-to-End Enterprise Production Scenarios for Nemawashi Multi-Agent Governance Engine (MEP-5.1).

Validates:
1. Scenario 1: Low-risk routine cache deployment -> UNANIMOUS_CONSENSUS
2. Scenario 2: Moderate-risk staging database migration -> CONDITIONAL_ALIGNMENT
3. Scenario 3: Destructive database drop -> CONSENSUS_VETO
4. Scenario 4: High-value GPU cluster expansion -> Non-blocking HITL suspension & gateway resumption
5. End-to-end cryptographic verification of the complete ledger hash chain.
"""

from pathlib import Path
import pytest

from nemawashi.audit.ledger import verify_ledger_chain
from nemawashi.core.engine import NemawashiEngine
from nemawashi.core.models import AgentProposal, StructuredAgentVote


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    """Isolate audit ledger and suspended states in temporary sandbox directories."""
    test_ledger = tmp_path / "e2e_ledger.jsonl"
    storage_dir = tmp_path / "suspended_states"
    test_cache = tmp_path / "test_cache.json"

    monkeypatch.setattr("nemawashi.audit.ledger.DEFAULT_LEDGER_PATH", test_ledger)
    monkeypatch.setattr("nemawashi.core.graph.SUSPENDED_STATES_DIR", storage_dir)
    monkeypatch.setattr("nemawashi.core.cache.DEFAULT_CACHE_PATH", test_cache)

    return {
        "ledger_path": test_ledger,
        "storage_dir": storage_dir,
        "cache_path": test_cache,
    }


def test_scenario_1_unanimous_consensus(isolated_environment):
    """Scenario 1: Routine Read-Replica Redis Cache Deployment."""
    engine = NemawashiEngine(max_rounds=3)
    proposal = AgentProposal(
        proposal_id="e2e-scen-1",
        proposing_agent="agent-infra-provisioner",
        action_type="cache_cluster_scale",
        action_description="Scale Redis read-replicas from 2 to 4 to dampen peak traffic latency.",
        target_resource="cache-redis-read-pool",
        estimated_cost_usd=45.0,
        estimated_blast_radius=15,
        parameters={"nodes": 4, "cluster_type": "redis-6.x"},
    )

    state = engine.evaluate_proposal(proposal)

    assert state.get("policy_passed") is True
    assert state.get("execution_permitted") is True
    assert state.get("resolution") is not None
    assert state["resolution"].verdict == "UNANIMOUS_CONSENSUS"
    assert state["resolution"].composite_risk_score < 25
    assert state.get("suspended_for_hitl") is False
    assert state.get("audit_committed") is True
    assert state.get("audit_record_hash") is not None

    # Verify all 4 stakeholders reviewed and voted APPROVE
    votes = state.get("stakeholder_votes", {})
    assert len(votes) == 4
    for sid in ["security", "compliance", "finops", "sre"]:
        assert sid in votes
        assert votes[sid].vote == "APPROVE"

    # Verify stakeholder_map
    s_map = state.get("stakeholder_map", {})
    assert all(s_map[s] == "APPROVE" for s in ["security", "compliance", "finops", "sre"])

    # Verify token metrics tracked
    assert state.get("prompt_tokens", 0) > 0
    assert state.get("completion_tokens", 0) > 0
    assert state.get("total_cost_usd", 0.0) > 0.0


def test_scenario_2_conditional_alignment(isolated_environment):
    """Scenario 2: Staging Database Schema Migration."""
    engine = NemawashiEngine(max_rounds=3)
    proposal = AgentProposal(
        proposal_id="e2e-scen-2",
        proposing_agent="agent-db-migrator",
        action_type="schema_migration_ddl",
        action_description="Execute schema DDL migration to add index on user_sessions table.",
        target_resource="staging-aurora-postgres",
        estimated_cost_usd=120.0,
        estimated_blast_radius=60,
        parameters={"table": "user_sessions", "ddl": "CREATE INDEX CONCURRENTLY idx_user_sess"},
    )

    state = engine.evaluate_proposal(proposal)

    assert state.get("policy_passed") is True
    assert state.get("execution_permitted") is True
    assert state.get("resolution") is not None
    assert state["resolution"].verdict == "CONDITIONAL_ALIGNMENT"
    assert len(state["resolution"].mandatory_mitigations) > 0
    assert state.get("suspended_for_hitl") is False
    assert state.get("audit_committed") is True

    # SRE or compliance should have issued MITIGATE with guardrail requirements
    votes = state.get("stakeholder_votes", {})
    assert votes["sre"].vote == "MITIGATE"
    assert any("rollback" in m.lower() for m in votes["sre"].mitigation_requirements)


def test_scenario_3_immediate_policy_veto(isolated_environment):
    """Scenario 3: Prohibited Destructive Operation (Hard Pre-check Veto)."""
    engine = NemawashiEngine(max_rounds=3)
    proposal = AgentProposal(
        proposal_id="e2e-scen-3",
        proposing_agent="agent-rogue-cleaner",
        action_type="drop_production_database",
        action_description="Emergency clean-up dropping orphaned tables in production database.",
        target_resource="prod-primary-db",
        estimated_cost_usd=0.0,
        estimated_blast_radius=95,
        parameters={"force": True},
    )

    state = engine.evaluate_proposal(proposal)

    assert state.get("policy_passed") is False
    assert state.get("execution_permitted") is False
    assert state.get("resolution") is not None
    assert state["resolution"].verdict == "CONSENSUS_VETO"
    assert len(state.get("policy_violations", [])) >= 2
    assert state.get("audit_committed") is True
    assert state.get("audit_record_hash") is not None

    # Stakeholder circle should have been bypassed
    assert len(state.get("stakeholder_votes", {})) == 0


def test_scenario_4_hitl_suspension_and_gateway_resumption(isolated_environment):
    """Scenario 4: High-Value Compute Expansion (Non-Blocking HITL Escalation & Resumption)."""
    engine = NemawashiEngine(max_rounds=3)
    proposal = AgentProposal(
        proposal_id="e2e-scen-4",
        proposing_agent="agent-capacity-autoscaler",
        action_type="compute_cluster_expansion",
        action_description="Provision GPU inference cluster with 8x H100 nodes for batch processing.",
        target_resource="prod-gpu-cluster-us-east",
        estimated_cost_usd=2400.0,
        estimated_blast_radius=85,
        parameters={"gpu_count": 8, "sku": "h100-80gb"},
    )

    # Stage 1: Initial evaluation triggers HITL escalation and suspends execution cleanly
    suspended_state = engine.evaluate_proposal(proposal)

    assert suspended_state.get("suspended_for_hitl") is True
    assert suspended_state.get("execution_permitted") is False
    assert suspended_state.get("audit_committed") is False
    assert suspended_state.get("resolution").verdict == "HUMAN_IN_THE_LOOP_ESCALATION"

    # Verify state was serialized to local storage
    storage_dir = isolated_environment["storage_dir"]
    state_file = storage_dir / f"{proposal.proposal_id}.json"
    assert state_file.exists()

    # Stage 2: Operator reviews deliberation out-of-band and posts approval
    resumed_state = engine.resume_proposal(
        proposal_id=proposal.proposal_id,
        approved=True,
        rationale="Executive VP approved after validating compute reservation budget",
        storage_dir=storage_dir,
    )

    assert resumed_state.get("suspended_for_hitl") is False
    assert resumed_state.get("human_approved") is True
    assert resumed_state.get("execution_permitted") is True
    assert resumed_state.get("audit_committed") is True
    assert resumed_state.get("audit_record_hash") is not None


def test_complete_cryptographic_ledger_verification(isolated_environment):
    """Verify unbroken SHA-256 hash chaining across sequential execution of all scenarios."""
    engine = NemawashiEngine(max_rounds=3)
    ledger_path = isolated_environment["ledger_path"]
    storage_dir = isolated_environment["storage_dir"]

    # 1. Run Scenario 1
    p1 = AgentProposal(
        proposal_id="p-chain-1",
        proposing_agent="agent-worker",
        action_type="scale_cache",
        action_description="Scale cache pool",
        target_resource="cache-pool",
        estimated_cost_usd=30.0,
        estimated_blast_radius=10,
    )
    engine.evaluate_proposal(p1)

    # 2. Run Scenario 2
    p2 = AgentProposal(
        proposal_id="p-chain-2",
        proposing_agent="agent-worker",
        action_type="schema_migration_ddl",
        action_description="Run schema ddl",
        target_resource="db-staging",
        estimated_cost_usd=100.0,
        estimated_blast_radius=50,
    )
    engine.evaluate_proposal(p2)

    # 3. Run Scenario 3 (Immediate Veto)
    p3 = AgentProposal(
        proposal_id="p-chain-3",
        proposing_agent="agent-rogue",
        action_type="drop_production_database",
        action_description="Drop primary db",
        target_resource="prod-primary-db",
        estimated_cost_usd=0.0,
        estimated_blast_radius=95,
    )
    engine.evaluate_proposal(p3)

    # 4. Run Scenario 4 (HITL with approval)
    p4 = AgentProposal(
        proposal_id="p-chain-4",
        proposing_agent="agent-autoscaler",
        action_type="gpu_cluster",
        action_description="Provision GPU fleet",
        target_resource="gpu-fleet",
        estimated_cost_usd=1500.0,
        estimated_blast_radius=85,
    )
    engine.evaluate_proposal(p4)
    engine.resume_proposal(
        proposal_id=p4.proposal_id,
        approved=True,
        rationale="Approved by platform lead",
        storage_dir=storage_dir,
    )

    # Mathematically verify the entire chain
    valid, message = verify_ledger_chain(ledger_path=ledger_path)
    assert valid is True, f"Ledger verification failed: {message}"
    assert "4 records intact" in message
