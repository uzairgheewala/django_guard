# ADR 0008 — Policies are versioned artifacts

## Decision

Performance budgets and their evaluations are canonical artifacts. Pytest, CLI, API, and UI use the
same policy schema and evaluation engine.

## Consequences

A CI failure has a durable policy definition, measured values, matched subjects, and provenance.
Frontend-only or decorator-only policy semantics are disallowed.
