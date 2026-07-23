# ADR 0016: Comparability precedes optimization claims

Status: Accepted for Milestone E.

## Decision

A baseline/candidate report must assess scenario, data-generating seed, environment, capture policy, and declared implementation changes before interpreting metrics.

Each dimension is classified as identical, compatible, controlled, confounding, or unknown. The report separately determines whether correctness, structural, plan, resource, and timing comparisons remain valid.

## Consequences

- uncontrolled timing changes are labeled advisory rather than causal;
- structural evidence may remain useful when timing is degraded;
- the UI must show changed dimensions before deltas;
- relative policies operate on a persisted comparison artifact rather than two unqualified numbers.
