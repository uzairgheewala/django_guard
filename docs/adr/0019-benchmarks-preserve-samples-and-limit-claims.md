# ADR 0019: Benchmarks preserve samples and limit claims

## Status

Accepted for Milestone G.

## Decision

PlanGuard persists every warm-up, measured, excluded, failed, and timed-out benchmark observation. Structural metrics and timing metrics remain separate. Scaling classifications describe only the measured range and never claim formal asymptotic complexity.

A benchmark protocol must declare warm-up count, measured iterations, cache protocol, ordering, outlier policy, timeout, and environmental controls. A series stores the original samples alongside robust summaries and comparability limitations.

## Consequences

The system can explain why a sample was excluded and can recompute summaries under future algorithms. Reports may remain inconclusive rather than manufacture certainty from sparse or unstable data.
