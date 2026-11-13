# ADR-004: Sequential Nemawashi Consensus Circle vs. Parallel Fan-Out

## Status
**ACCEPTED** (2026-11-12)

## Context
When autonomous AI agents initiate complex cloud operations (e.g., cluster auto-scaling, database index migration, IAM policy reconfiguration), governance engines commonly employ one of two orchestration patterns:
1. **Parallel Fan-Out**: Broadcasting the proposal concurrently to Security, Compliance, FinOps, and SRE agents, then aggregating votes in a parallel join node.
2. **Sequential Consensus Circle (*Nemawashi*)**: Reviewing proposals sequentially through domain stakeholders where each subsequent reviewer inspects upstream votes and required mitigations.

In prototype implementations of parallel voting, we observed systemic mitigation collisions:
- FinOps demanded cost reduction via AWS Spot instances.
- SRE independently demanded high availability with On-Demand multi-AZ instances.
- The Arbiter received mutually incompatible, contradictory mitigation sets without prior cross-stakeholder negotiation context, triggering unnecessary deliberation deadlocks and human escalations.

## Decision
We adopted a strictly **sequential multi-agent deliberation circle** inspired by Japanese corporate *Nemawashi* (根回し - laying the groundwork):
1. **Evaluation Order**: Security Guardian $\rightarrow$ Compliance Auditor $\rightarrow$ FinOps Custodian $\rightarrow$ Reliability (SRE) Guardian $\rightarrow$ Arbiter Synthesis.
2. **Context Accumulation**: Downstream stakeholders receive the full, immutable upstream vote history (`votes` and `stakeholder_votes`), allowing FinOps and SRE to formulate mutually coherent mitigations (e.g., spot instances for worker nodes paired with on-demand instances for control plane quorum).
3. **Targeted Rightsizing**: Cost optimization intercepts the proposal only after FinOps and SRE have registered their constraints, ensuring parameter mutations preserve baseline reliability.

## Consequences

### Positive
- **Zero Mitigation Deadlocks**: Downstream agents tailor recommendations to accommodate upstream security and compliance boundaries.
- **Lower Token Overhead**: Avoids redundant conflicting deliberation loops between FinOps and SRE.
- **Deterministic Audit Trail**: Each vote explicitly captures the chronological state of consensus at the exact moment of review.

### Negative
- **Marginally Higher End-to-End Latency**: Sequential execution incurs an additive $O(N)$ execution time ($< 1.5\text{s}$ offline, $\sim 4\text{s}$ live) compared to parallel fan-out ($O(1)$). This trade-off is mitigated by the pre-circle Semantic Vector Cache, which bypasses the entire circle for equivalent proposals in $< 10\text{ms}$.
