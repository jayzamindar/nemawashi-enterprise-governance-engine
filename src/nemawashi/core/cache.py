"""Local Semantic Vector Caching Engine for Proposal Deliberation.

Caches proposal resolutions and historical stakeholder votes using vector similarity.
Bypasses the multi-agent deliberation circle for semantically equivalent proposals
(cosine similarity >= 0.95), reducing latency to near-zero and eliminating redundant
token costs while preserving full audit vote lineage.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from filelock import FileLock

from nemawashi.core.models import AgentProposal, Resolution, StructuredAgentVote

DEFAULT_CACHE_DIR = Path(os.environ.get("NEMAWASHI_CACHE_DIR", "cache"))
DEFAULT_CACHE_PATH = DEFAULT_CACHE_DIR / "semantic_cache.json"


def get_enterprise_rules_hash(rules_path: Optional[Path] = None) -> str:
    """Compute deterministic SHA-256 hash of enterprise_rules.json for cache invalidation."""
    path = rules_path or (Path(__file__).parent.parent / "policies" / "enterprise_rules.json")
    if path.exists():
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except Exception:
            pass
    return "genesis_rules_hash"


@dataclass
class CacheEntry:
    """Internal schema for serialized cache record."""

    proposal_id: str
    action_type: str
    target_resource: str
    action_description: str
    embedding: List[float]
    resolution: Dict[str, Any]
    stakeholder_votes: Dict[str, Dict[str, Any]]
    deliberation_round: int
    cached_at: str
    rules_hash: str


@dataclass
class CacheMatch:
    """Represents a successful semantic cache match with restored vote lineage."""

    similarity: float
    resolution: Resolution
    cached_proposal_id: str
    cached_at: str
    stakeholder_votes: Dict[str, StructuredAgentVote] = field(default_factory=dict)
    deliberation_round: int = 1
    rules_hash: str = ""


# Alias for backward compatibility and TRD naming
CacheLookupResult = CacheMatch


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
    """Persistent local semantic cache for evaluated proposals with cross-platform mutex locking."""

    def __init__(self, cache_path: Optional[Path] = None, similarity_threshold: float = 0.95):
        self.cache_path = cache_path or DEFAULT_CACHE_PATH
        self.similarity_threshold = similarity_threshold
        self._entries: List[Dict[str, Any]] = []
        self._lock = FileLock(f"{self.cache_path}.lock", timeout=10)
        self._load()

    def _read_disk(self) -> None:
        """Internal disk reader executed within an acquired lock."""
        if not self.cache_path.exists():
            self._entries = []
            return
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                self._entries = json.load(f)
        except Exception:
            self._entries = []

    def _write_disk(self) -> None:
        """Internal disk writer executed within an acquired lock."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self._entries, f, indent=2)

    def _load(self) -> None:
        """Load cache entries under mutex lock."""
        with self._lock:
            self._read_disk()

    def _save(self) -> None:
        """Save cache entries under mutex lock."""
        with self._lock:
            self._write_disk()

    def _get_embedding_text(self, proposal: AgentProposal) -> str:
        return f"{proposal.action_type} {proposal.target_resource} {proposal.action_description}"

    def lookup(self, proposal: AgentProposal) -> Optional[CacheMatch]:
        """Query cache for an identical or semantically equivalent proposal.

        Validates 24-hour TTL and enterprise rules hash matching before accepting match.
        Restores full StructuredAgentVote lineage to prevent consensus amnesia.
        """
        with self._lock:
            self._read_disk()
            query_text = self._get_embedding_text(proposal)
            query_vec = compute_text_embedding(query_text)

            best_match: Optional[CacheMatch] = None
            highest_sim = 0.0
            current_rules_hash = get_enterprise_rules_hash()

            for entry in self._entries:
                # 1. Action type compatibility
                if entry.get("action_type") != proposal.action_type:
                    continue

                # 2. Invalidation Check: 24-Hour TTL (TRD-3.2)
                cached_at_str = entry.get("cached_at")
                if cached_at_str:
                    try:
                        cached_dt = datetime.fromisoformat(cached_at_str)
                        if (datetime.now(timezone.utc) - cached_dt).total_seconds() > 86400:
                            continue
                    except Exception:
                        pass

                # 3. Invalidation Check: Rules Hash Matching (TRD-3.2)
                entry_rules_hash = entry.get("rules_hash")
                if entry_rules_hash and entry_rules_hash != current_rules_hash:
                    continue

                # 4. Cosine similarity evaluation
                entry_vec = entry.get("embedding", [])
                sim = cosine_similarity(query_vec, entry_vec)

                if sim >= self.similarity_threshold and sim > highest_sim:
                    highest_sim = sim
                    resolution_dict = entry.get("resolution", {})
                    res = Resolution.model_validate(resolution_dict)

                    # 5. Restore Vote Lineage with backward compatibility (TRD-3.3)
                    raw_votes = entry.get("stakeholder_votes", {})
                    restored_votes: Dict[str, StructuredAgentVote] = {}
                    if isinstance(raw_votes, dict):
                        for k, v in raw_votes.items():
                            if isinstance(v, dict):
                                try:
                                    restored_votes[k] = StructuredAgentVote.model_validate(v)
                                except Exception:
                                    pass
                            elif isinstance(v, StructuredAgentVote):
                                restored_votes[k] = v

                    delib_round = int(entry.get("deliberation_round", 1))

                    best_match = CacheMatch(
                        similarity=round(sim, 4),
                        resolution=res,
                        cached_proposal_id=entry.get("proposal_id", "unknown"),
                        cached_at=entry.get("cached_at", ""),
                        stakeholder_votes=restored_votes,
                        deliberation_round=delib_round,
                        rules_hash=entry.get("rules_hash", ""),
                    )

            return best_match

    def store(
        self,
        proposal: AgentProposal,
        resolution: Resolution,
        stakeholder_votes: Optional[Dict[str, Any]] = None,
        deliberation_round: int = 1,
    ) -> None:
        """Persist a newly deliberated proposal resolution into the semantic cache with full vote lineage."""
        embedding_text = self._get_embedding_text(proposal)
        vec = compute_text_embedding(embedding_text)

        with self._lock:
            self._read_disk()

            # Do not store duplicate identical proposal IDs
            for entry in self._entries:
                if entry.get("proposal_id") == proposal.proposal_id:
                    return

            # Normalize serialized votes map for lineage retention
            serialized_votes: Dict[str, Dict[str, Any]] = {}
            if stakeholder_votes:
                for k, v in stakeholder_votes.items():
                    if isinstance(v, StructuredAgentVote):
                        serialized_votes[k] = v.model_dump()
                    elif isinstance(v, dict):
                        serialized_votes[k] = v

            new_entry = {
                "proposal_id": proposal.proposal_id,
                "action_type": proposal.action_type,
                "target_resource": proposal.target_resource,
                "action_description": proposal.action_description,
                "embedding": vec,
                "resolution": resolution.model_dump(),
                "stakeholder_votes": serialized_votes,
                "deliberation_round": deliberation_round,
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "rules_hash": get_enterprise_rules_hash(),
            }

            self._entries.append(new_entry)
            self._write_disk()

    def clear(self) -> None:
        """Purge all cached entries safely using mutex lock."""
        with self._lock:
            self._entries = []
            if self.cache_path.exists():
                try:
                    os.remove(self.cache_path)
                except OSError:
                    pass
