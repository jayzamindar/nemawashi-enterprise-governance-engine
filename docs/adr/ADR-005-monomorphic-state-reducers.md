# ADR-005: Monomorphic State Channel Reducers and Consensus Memory Invariance

## Status
**ACCEPTED** (2026-11-12)

## Context
In LangGraph `StateGraph` architectures, state propagation across sequential nodes relies on channel reducers. If channels are unmanaged or loosely typed:
1. **Consensus Amnesia**: A node returning `{"votes": [new_vote]}` inadvertently replaces and overwrites the entire accumulated list of votes from upstream stakeholders, erasing historical voting records.
2. **Polymorphic List Confusion**: Allowing reducers to accept either a single object OR a collection (`Union[T, List[T]]`) creates subtle edge cases where nodes accidentally inject batch lists, causing uncoordinated vote inflation, duplicate entries, or nested list hierarchies (`[[vote1], vote2]`).
3. **In-Place Mutation Bleed**: Python references passed between nodes can be mutated downstream, retroactively altering earlier stakeholder verdicts and invalidating cryptographic audit signatures.

## Decision
We enforce **monomorphic, strictly typed channel reducers** and deep copy isolation across all state channels:
1. **Monomorphic Signature**: `append_vote(existing: Optional[List[StructuredAgentVote]], new_vote: StructuredAgentVote) -> List[StructuredAgentVote]` strictly accepts ONLY a singular `StructuredAgentVote` instance.
2. **Boundary Type Enforcement**: If a list or tuple is passed to `append_vote`, it immediately raises a `TypeError` at runtime, completely rejecting batch polymorphism.
3. **Deep Copy Isolation**: Input votes and existing lists are deep-copied (`copy.deepcopy`) upon receipt and return, guaranteeing that subsequent node executions cannot mutate committed historical votes.
4. **Frozen Inter-Agent Contracts**: `StructuredAgentVote` enforces `ConfigDict(extra="forbid", frozen=True)`. Once emitted, a vote's memory address is immutable.

## Consequences

### Positive
- **Guaranteed Immutability**: Historical votes cannot be manipulated, truncated, or overwritten by downstream agents or loop iterations.
- **Fail-Fast Boundary Validation**: Any node emitting improper batch payloads is immediately halted by a `TypeError` during CI testing rather than silently corrupting state.
- **Cryptographic Audit Determinism**: SHA-256 ledger block hashing relies on deterministic vote serialization; immutable inputs prevent hash discrepancies.

### Negative
- **Marginal Memory Allocation**: Deep-copying small Pydantic objects adds negligible memory allocation overhead, which is inconsequential for enterprise governance payloads ($< 50\text{KB}$).
