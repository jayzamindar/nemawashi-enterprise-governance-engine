"""Tests for Semantic Proposal Vector Cache Guardrail & Vote Lineage (TRD-3)."""

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest

from nemawashi.audit.ledger import verify_ledger_chain
from nemawashi.core.cache import (
    SemanticProposalCache,
    compute_text_embedding,
    cosine_similarity,
)
from nemawashi.core.engine import NemawashiEngine
from nemawashi.core.models import AgentProposal, Resolution, StructuredAgentVote


def test_text_embedding_properties():
    """Verify vector embedding characteristics."""
    text1 = "scale redis read-replica cluster from 2 to 4 nodes"
    text2 = "scale redis read-replica cluster from 2 to 4 nodes"
    text3 = "drop production database root credentials"

    vec1 = compute_text_embedding(text1)
    vec2 = compute_text_embedding(text2)
    vec3 = compute_text_embedding(text3)

    assert len(vec1) == 64
    assert vec1 == vec2  # Deterministic

    # Cosine similarity of identical text must be 1.0
    sim_identical = cosine_similarity(vec1, vec2)
    assert abs(sim_identical - 1.0) < 1e-4

    # Cosine similarity of dissimilar text must be lower
    sim_dissimilar = cosine_similarity(vec1, vec3)
    assert sim_dissimilar < 0.6


def test_semantic_cache_store_and_lookup(tmp_path):
    """Verify persistent cache store and high-confidence lookup with vote lineage."""
    cache_file = tmp_path / "test_semantic_cache.json"
    cache = SemanticProposalCache(cache_path=cache_file, similarity_threshold=0.90)

    proposal = AgentProposal(
        proposal_id="p-cache-1",
        proposing_agent="agent-infra",
        action_type="scale_cache",
        action_description="Scale redis cache replicas in staging environment",
        target_resource="redis-staging-cluster",
    )
    resolution = Resolution(
        proposal_id="p-cache-1",
        verdict="UNANIMOUS_CONSENSUS",
        composite_risk_score=12,
        summary="Cached approval",
    )
    mock_votes = {
        "security": StructuredAgentVote(
            stakeholder_id="security",
            vote="APPROVE",
            risk_tags=["low_risk"],
            mitigation_requirements=[],
        ),
        "finops": StructuredAgentVote(
            stakeholder_id="finops",
            vote="APPROVE",
            risk_tags=["budget_ok"],
            mitigation_requirements=[],
        ),
    }

    # 1. Initial lookup is miss
    assert cache.lookup(proposal) is None

    # 2. Store resolution with vote lineage
    cache.store(proposal, resolution, stakeholder_votes=mock_votes, deliberation_round=1)

    # 3. Lookup identical proposal is hit and restores vote lineage
    match = cache.lookup(proposal)
    assert match is not None
    assert match.similarity >= 0.95
    assert match.resolution.verdict == "UNANIMOUS_CONSENSUS"
    assert match.cached_proposal_id == "p-cache-1"
    assert "security" in match.stakeholder_votes
    assert "finops" in match.stakeholder_votes
    assert match.stakeholder_votes["security"].vote == "APPROVE"
    assert match.deliberation_round == 1

    # 4. Lookup with minor phrasing variations still matches above threshold
    similar_proposal = AgentProposal(
        proposal_id="p-cache-2",
        proposing_agent="agent-worker",
        action_type="scale_cache",
        action_description="Scale redis cache replicas in staging environment now",
        target_resource="redis-staging-cluster",
    )
    match_sim = cache.lookup(similar_proposal)
    assert match_sim is not None
    assert match_sim.similarity >= 0.90
    assert "security" in match_sim.stakeholder_votes

    # 5. Lookup completely different proposal misses
    diff_proposal = AgentProposal(
        proposal_id="p-cache-3",
        proposing_agent="agent-rogue",
        action_type="delete_backup",
        action_description="Delete all s3 backups immediately",
        target_resource="backup-vault",
    )
    assert cache.lookup(diff_proposal) is None

    # 6. Persistence across cache re-instantiation
    cache2 = SemanticProposalCache(cache_path=cache_file, similarity_threshold=0.90)
    match2 = cache2.lookup(proposal)
    assert match2 is not None
    assert match2.resolution.verdict == "UNANIMOUS_CONSENSUS"
    assert match2.stakeholder_votes["finops"].vote == "APPROVE"

    # 7. Clear cache
    cache2.clear()
    assert cache2.lookup(proposal) is None


def test_semantic_cache_ttl_expiration(tmp_path):
    """Verify that cache entries exceeding the 24-hour TTL window are invalidated (TRD-3.2)."""
    cache_file = tmp_path / "ttl_cache.json"
    cache = SemanticProposalCache(cache_path=cache_file)

    proposal = AgentProposal(
        proposal_id="p-ttl",
        proposing_agent="agent-infra",
        action_type="scale_cache",
        action_description="Scale redis cache replicas",
        target_resource="redis-cluster",
    )
    resolution = Resolution(
        proposal_id="p-ttl",
        verdict="UNANIMOUS_CONSENSUS",
        composite_risk_score=10,
        summary="Approved",
    )
    cache.store(proposal, resolution)
    assert cache.lookup(proposal) is not None

    # Artificially age the entry past 24 hours
    with open(cache_file, "r", encoding="utf-8") as f:
        entries = json.load(f)
    entries[0]["cached_at"] = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc).isoformat()
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(entries, f)

    # Expired entry must be skipped
    assert cache.lookup(proposal) is None


def test_semantic_cache_rules_hash_invalidation(tmp_path):
    """Verify that modifying enterprise rules invalidates matching cache entries (TRD-3.2)."""
    cache_file = tmp_path / "rules_cache.json"
    cache = SemanticProposalCache(cache_path=cache_file)

    proposal = AgentProposal(
        proposal_id="p-rules",
        proposing_agent="agent-infra",
        action_type="scale_cache",
        action_description="Scale redis cache replicas",
        target_resource="redis-cluster",
    )
    resolution = Resolution(
        proposal_id="p-rules",
        verdict="UNANIMOUS_CONSENSUS",
        composite_risk_score=10,
        summary="Approved",
    )
    cache.store(proposal, resolution)
    assert cache.lookup(proposal) is not None

    # Simulate tampered / modified enterprise policy rules
    with open(cache_file, "r", encoding="utf-8") as f:
        entries = json.load(f)
    entries[0]["rules_hash"] = "stale_policy_hash_override"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(entries, f)

    # Mismatched rules hash must invalidate entry to prevent stale bypasses
    assert cache.lookup(proposal) is None


def test_semantic_cache_hit_preserves_vote_lineage_in_audit_ledger(tmp_path, monkeypatch):
    """Verify end-to-end that cache hits restore 4-stakeholder vote lineage in state and ledger."""
    ledger_file = tmp_path / "cache_lineage_ledger.jsonl"
    cache_file = tmp_path / "cache_lineage_cache.json"

    monkeypatch.setattr("nemawashi.audit.ledger.DEFAULT_LEDGER_PATH", ledger_file)
    monkeypatch.setattr("nemawashi.core.cache.DEFAULT_CACHE_PATH", cache_file)

    engine = NemawashiEngine(max_rounds=3)

    # 1. First evaluation: cache miss -> full deliberation circle through 4 stakeholders
    proposal1 = AgentProposal(
        proposal_id="p-lineage-1",
        proposing_agent="agent-worker",
        action_type="scale_cache",
        action_description="Scale redis cache replicas in staging environment",
        target_resource="redis-staging-cluster",
        estimated_cost_usd=20.0,
        estimated_blast_radius=10,
    )

    state1 = engine.evaluate_proposal(proposal1)
    assert state1.get("cache_hit") is False
    assert state1.get("audit_committed") is True
    votes1 = state1.get("stakeholder_votes", {})
    assert set(votes1.keys()) == {"security", "compliance", "finops", "sre"}

    # 2. Second evaluation: identical proposal -> cache hit
    proposal2 = AgentProposal(
        proposal_id="p-lineage-2",
        proposing_agent="agent-worker",
        action_type="scale_cache",
        action_description="Scale redis cache replicas in staging environment",
        target_resource="redis-staging-cluster",
        estimated_cost_usd=20.0,
        estimated_blast_radius=10,
    )

    state2 = engine.evaluate_proposal(proposal2)
    assert state2.get("cache_hit") is True
    assert state2.get("audit_committed") is True
    votes2 = state2.get("stakeholder_votes", {})
    assert set(votes2.keys()) == {"security", "compliance", "finops", "sre"}
    for role in ("security", "compliance", "finops", "sre"):
        assert votes2[role].vote == votes1[role].vote
        assert votes2[role].stakeholder_id == votes1[role].stakeholder_id

    # Verify stakeholder_map is also populated on cache hit
    s_map = state2.get("stakeholder_map", {})
    assert set(s_map.keys()) == {"security", "compliance", "finops", "sre"}
    for role in ("security", "compliance", "finops", "sre"):
        assert s_map[role] == votes2[role].vote

    # 3. Verify ledger records and cryptographic chain
    assert ledger_file.exists()
    records = []
    with open(ledger_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line.strip()))

    assert len(records) == 2
    # Record 0: Cache miss, full votes
    assert records[0]["index"] == 0
    assert records[0]["cache_hit"] is False
    assert set(records[0]["stakeholder_votes"].keys()) == {"security", "compliance", "finops", "sre"}

    # Record 1: Cache hit, restored full votes
    assert records[1]["index"] == 1
    assert records[1]["cache_hit"] is True
    assert set(records[1]["stakeholder_votes"].keys()) == {"security", "compliance", "finops", "sre"}

    # Verify cryptographic integrity of both records in the chain
    valid, msg = verify_ledger_chain(ledger_file)
    assert valid is True, f"Ledger verification failed: {msg}"
    assert "2 records intact" in msg
