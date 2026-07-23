# ADR 0017: Universe coverage is declared and constrained

Status: Accepted for Milestone F.

## Context

PlanGuard needs to describe how representative its scenario corpus is without claiming to enumerate an unbounded SQL, workload, data-state, and execution-plan space. A raw Cartesian product is both intractable and semantically wrong because many combinations are impossible, inapplicable, or unsupported.

## Decision

Coverage is always evaluated relative to a versioned `UniverseProfileArtifact`. A profile declares typed axes, representative partitions, constraints, target capabilities, and coverage strategies. Coverage obligations are partial coordinates such as one-axis partitions, selected pairwise interactions, mutation classes, motifs, and metamorphic relations rather than every complete point in a Cartesian product.

Every coverage cell has one explicit state:

- `covered`;
- `uncovered`;
- `inapplicable`;
- `unsupported`;
- `unknown`.

Representative generation is deterministic for a fixed profile, catalog, strategy set, maximum case count, and seed. Selection uses risk-weighted marginal coverage and records the exact obligations contributed by each selected case.

## Consequences

- Coverage claims are precise and auditable.
- Unsupported and inapplicable cells are not misreported as test failures.
- Applications can extend domains and constraints without changing the core schema.
- The selected corpus is compact but cannot be interpreted as theoretical completeness.
- Any report must retain the universe profile and generation provenance that define its denominator.
