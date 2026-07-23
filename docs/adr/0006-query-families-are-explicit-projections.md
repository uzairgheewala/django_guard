# ADR 0006 — Query families are explicit projections

## Decision

There is no universal built-in query family. Every observed family names a `family_scheme_key` and
records its dimension values and member execution references.

## Consequences

The same run can be regrouped without losing evidence. Detectors and policies must declare the
lens they use. Stable query-shape fingerprints remain features, not artifact identities.
