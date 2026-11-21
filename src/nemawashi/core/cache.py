"""Local Semantic Vector Caching Engine for Proposal Deliberation.

Caches proposal resolutions and historical stakeholder votes using vector similarity.
Bypasses the multi-agent deliberation circle for semantically equivalent proposals
(cosine similarity >= 0.95), reducing latency to near-zero and eliminating redundant
token costs while preserving full audit vote lineage.
"""

import hashlib
import json
import logging
import math
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from filelock import FileLock

from nemawashi.core.models import AgentProposal, Resolution, StructuredAgentVote

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path(os.environ.get("NEMAWASHI_CACHE_DIR", "cache"))
DEFAULT_CACHE_PATH = DEFAULT_CACHE_DIR / "semantic_cache.json"
CACHE_TTL_SECONDS = 86400
MAX_CACHE_ENTRIES = 1000


def get_enterprise_rules_hash(rules_path: Path | None = None) -> str:
    """Compute deterministic SHA-256 hash of enterprise_rules.json for cache invalidation."""
    path = rules_path or (
        Path(__file__).parent.parent / "policies" / "enterprise_rules.json"
    )
    if path.exists():
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            logger.warning("Failed to hash enterprise rules at %s: %s", path, exc)
    return "genesis_rules_hash"


@dataclass
class CacheEntry:
    """Internal schema for serialized cache record."""

    proposal_id: str
    action_type: str
    target_resource: str
    action_description: str
    embedding: list[float]
    resolution: dict[str, Any]
    stakeholder_votes: dict[str, dict[str, Any]]
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
    stakeholder_votes: dict[str, StructuredAgentVote] = field(default_factory=dict)
    deliberation_round: int = 1
    rules_hash: str = ""


# Alias for backward compatibility and TRD naming
CacheLookupResult = CacheMatch


def _deterministic_hash_index(token: str, dim: int) -> int:
    """Map a token deterministically to a bucket in [0, dim) using SHA-256."""
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % dim


def compute_text_embedding(text: str, dim: int = 64) -> list[float]:
    """Compute a deterministic, normalized vector embedding for text.

    Uses SHA-256 token and bi-gram feature hashing to produce a stable
    unit vector suitable for cosine similarity comparisons across restarts.
    """
    clean_text = text.lower().strip()
    words = re.findall(r"\w+", clean_text)
    vec = [0.0] * dim

    # Populate feature vector using deterministic SHA-256 word and bi-gram hashing
    for word in words:
        h = _deterministic_hash_index(word, dim)
        vec[h] += 1.0

    for i in range(len(words) - 1):
        bigram = f"{words[i]}_{words[i + 1]}"
        h = _deterministic_hash_index(bigram, dim)
        vec[h] += 1.5

    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return [0.0] * dim
    return [round(x / norm, 6) for x in vec]


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity between two normalized vectors."""
    if len(v1) != len(v2) or not v1 or not v2:
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2, strict=True))
    return max(0.0, min(1.0, dot_product))


def _is_entry_expired(
    entry: dict[str, Any], now: datetime, ttl_seconds: int = CACHE_TTL_SECONDS
) -> bool:
    """Return True if a cache entry is missing, malformed, or older than ttl_seconds."""
    cached_at_str = entry.get("cached_at")
    if not isinstance(cached_at_str, str) or not cached_at_str.strip():
        return True
    try:
        cached_dt = datetime.fromisoformat(cached_at_str)
    except ValueError:
        return True
    if cached_dt.tzinfo is None:
        cached_dt = cached_dt.replace(tzinfo=UTC)
    return (now - cached_dt).total_seconds() > ttl_seconds


class SemanticProposalCache:
    """Persistent local semantic cache for evaluated proposals with cross-platform mutex locking."""

    def __init__(
        self,
        cache_path: Path | None = None,
        similarity_threshold: float = 0.95,
        max_entries: int = MAX_CACHE_ENTRIES,
    ):
        self.cache_path = cache_path or DEFAULT_CACHE_PATH
        self.similarity_threshold = similarity_threshold
        self.max_entries = max(1, max_entries)
        self._entries: list[dict[str, Any]] = []
        self._load()

    def _acquire_lock(self) -> FileLock:
        """Instantiate a fresh per-operation FileLock for cross-platform mutex safety."""
        return FileLock(f"{self.cache_path}.lock", timeout=10)

    def _read_disk(self) -> None:
        """Internal disk reader executed within an acquired lock."""
        if not self.cache_path.exists():
            self._entries = []
            return
        try:
            with open(self.cache_path, encoding="utf-8") as f:
                self._entries = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "Failed to read semantic cache at %s: %s", self.cache_path, exc
            )
            self._entries = []

    def _write_disk(self) -> None:
        """Internal disk writer executed within an acquired lock."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self._entries, f, indent=2)

    def _load(self) -> None:
        """Load cache entries under mutex lock."""
        with self._acquire_lock():
            self._read_disk()

    def _save(self) -> None:
        """Save cache entries under mutex lock."""
        with self._acquire_lock():
            self._write_disk()

    def _get_embedding_text(self, proposal: AgentProposal) -> str:
        return f"{proposal.action_type} {proposal.target_resource} {proposal.action_description}"

    def lookup(self, proposal: AgentProposal) -> CacheMatch | None:
        """Query cache for an identical or semantically equivalent proposal.

        Validates 24-hour TTL and enterprise rules hash matching before accepting match.
        Restores full StructuredAgentVote lineage to prevent consensus amnesia.
        """
        with self._acquire_lock():
            self._read_disk()
            query_text = self._get_embedding_text(proposal)
            query_vec = compute_text_embedding(query_text)

            best_match: CacheMatch | None = None
            highest_sim = 0.0
            current_rules_hash = get_enterprise_rules_hash()
            now = datetime.now(UTC)

            for entry in self._entries:
                # 1. Action type compatibility
                if entry.get("action_type") != proposal.action_type:
                    continue

                # 2. Invalidation Check: 24-Hour TTL (TRD-3.2)
                if entry.get("cached_at") and _is_entry_expired(entry, now):
                    continue

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
                    restored_votes: dict[str, StructuredAgentVote] = {}
                    if isinstance(raw_votes, dict):
                        for k, v in raw_votes.items():
                            if isinstance(v, dict):
                                try:
                                    restored_votes[k] = (
                                        StructuredAgentVote.model_validate(v)
                                    )
                                except ValueError:
                                    continue
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
        stakeholder_votes: dict[str, Any] | None = None,
        deliberation_round: int = 1,
    ) -> None:
        """Persist a newly deliberated proposal resolution into the semantic cache with full vote lineage.

        Prunes expired (>24h) entries and enforces max_entries ceiling on every store().
        """
        embedding_text = self._get_embedding_text(proposal)
        vec = compute_text_embedding(embedding_text)

        with self._acquire_lock():
            self._read_disk()

            now = datetime.now(UTC)
            before_count = len(self._entries)
            self._entries = [
                entry for entry in self._entries if not _is_entry_expired(entry, now)
            ]
            pruned_expired = len(self._entries) != before_count

            # Do not store duplicate identical proposal IDs
            for entry in self._entries:
                if entry.get("proposal_id") == proposal.proposal_id:
                    if pruned_expired:
                        self._write_disk()
                    return

            # Normalize serialized votes map for lineage retention
            serialized_votes: dict[str, dict[str, Any]] = {}
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
                "cached_at": now.isoformat(),
                "rules_hash": get_enterprise_rules_hash(),
            }

            self._entries.append(new_entry)
            if len(self._entries) > self.max_entries:
                self._entries = self._entries[-self.max_entries :]
            self._write_disk()

    def clear(self) -> None:
        """Purge all cached entries safely using mutex lock."""
        with self._acquire_lock():
            self._entries = []
            if self.cache_path.exists():
                try:
                    os.remove(self.cache_path)
                except OSError as exc:
                    logger.warning(
                        "Failed to remove cache file %s: %s", self.cache_path, exc
                    )
