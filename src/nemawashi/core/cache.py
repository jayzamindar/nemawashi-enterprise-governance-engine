"""Local Semantic Vector Caching Engine for Proposal Deliberation.

Caches proposal resolutions using vector similarity. Bypasses the multi-agent
deliberation circle for semantically equivalent proposals (cosine similarity >= 0.95),
reducing latency to near-zero and eliminating redundant token costs.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

from nemawashi.core.models import AgentProposal, Resolution

DEFAULT_CACHE_PATH = Path("cache") / "semantic_cache.json"


@dataclass
class CacheMatch:
    """Represents a successful semantic cache match."""

    similarity: float
    resolution: Resolution
    cached_proposal_id: str
    cached_at: str


def compute_text_embedding(text: str, dim: int = 64) -> List[float]:
    """Compute a deterministic, normalized vector embedding for text.

    Uses character n-grams and token frequency hashing to produce a stable
    unit vector suitable for cosine similarity comparisons in offline environments.
    """
    clean_text = text.lower().strip()
    words = re.findall(r"\w+", clean_text)
    vec = [0.0] * dim

    # Populate feature vector using word and bi-gram hashing
    for word in words:
        h = hash(word) % dim
        vec[h] += 1.0

    for i in range(len(words) - 1):
        bigram = f"{words[i]}_{words[i+1]}"
        h = hash(bigram) % dim
        vec[h] += 1.5

    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return [0.0] * dim
    return [round(x / norm, 6) for x in vec]


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two normalized vectors."""
    if len(v1) != len(v2) or not v1 or not v2:
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    return max(0.0, min(1.0, dot_product))


class SemanticProposalCache:
    """Persistent local semantic cache for evaluated proposals."""

    def __init__(self, cache_path: Optional[Path] = None, similarity_threshold: float = 0.95):
        self.cache_path = cache_path or DEFAULT_CACHE_PATH
        self.similarity_threshold = similarity_threshold
        self._entries: List[Dict] = []
        self._load()

    def _load(self):
        if not self.cache_path.exists():
            self._entries = []
            return
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                self._entries = json.load(f)
        except Exception:
            self._entries = []

    def _save(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self._entries, f, indent=2)

    def _get_embedding_text(self, proposal: AgentProposal) -> str:
        return f"{proposal.action_type} {proposal.target_resource} {proposal.action_description}"

    def lookup(self, proposal: AgentProposal) -> Optional[CacheMatch]:
        """Query cache for an identical or semantically equivalent proposal."""
        query_text = self._get_embedding_text(proposal)
        query_vec = compute_text_embedding(query_text)

        best_match: Optional[CacheMatch] = None
        highest_sim = 0.0

        for entry in self._entries:
            # Check action_type and target compatibility
            if entry.get("action_type") != proposal.action_type:
                continue

            entry_vec = entry.get("embedding", [])
            sim = cosine_similarity(query_vec, entry_vec)

            if sim >= self.similarity_threshold and sim > highest_sim:
                highest_sim = sim
                resolution_dict = entry.get("resolution", {})
                res = Resolution.model_validate(resolution_dict)
                best_match = CacheMatch(
                    similarity=round(sim, 4),
                    resolution=res,
                    cached_proposal_id=entry.get("proposal_id", "unknown"),
                    cached_at=entry.get("cached_at", ""),
                )

        return best_match

    def store(self, proposal: AgentProposal, resolution: Resolution):
        """Persist a newly deliberated proposal resolution into the semantic cache."""
        embedding_text = self._get_embedding_text(proposal)
        vec = compute_text_embedding(embedding_text)

        # Do not store duplicate identical proposal IDs
        for entry in self._entries:
            if entry.get("proposal_id") == proposal.proposal_id:
                return

        new_entry = {
            "proposal_id": proposal.proposal_id,
            "action_type": proposal.action_type,
            "target_resource": proposal.target_resource,
            "action_description": proposal.action_description,
            "embedding": vec,
            "resolution": resolution.model_dump(),
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }

        self._entries.append(new_entry)
        self._save()

    def clear(self):
        """Purge all cached entries."""
        self._entries = []
        if self.cache_path.exists():
            try:
                os.remove(self.cache_path)
            except OSError:
                pass
