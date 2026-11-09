"""Tests for Semantic Proposal Vector Cache Guardrail (MEP-2.2)."""

from nemawashi.core.cache import (
    SemanticProposalCache,
    compute_text_embedding,
    cosine_similarity,
)
from nemawashi.core.models import AgentProposal, Resolution


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
    """Verify persistent cache store and high-confidence lookup."""
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

    # 1. Initial lookup is miss
    assert cache.lookup(proposal) is None

    # 2. Store resolution
    cache.store(proposal, resolution)

    # 3. Lookup identical proposal is hit
    match = cache.lookup(proposal)
    assert match is not None
    assert match.similarity >= 0.95
    assert match.resolution.verdict == "UNANIMOUS_CONSENSUS"
    assert match.cached_proposal_id == "p-cache-1"

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

    # 7. Clear cache
    cache2.clear()
    assert cache2.lookup(proposal) is None
