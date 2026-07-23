# ADR 0013: Scenario phases always produce receipts

## Status
Accepted for Milestone D.

## Decision
Preparation, dataset generation, mutation, operation execution, oracle evaluation, and cleanup each
produce an immutable phase receipt. Failure produces a failed receipt and does not suppress cleanup.

## Consequences
Partial and failed experiments remain inspectable. “Nothing happened” can be distinguished from
“nothing was evaluated,” and every output retains phase-level provenance.
