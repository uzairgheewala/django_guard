# ADR 0003: Open registries and explicit capability gaps

- Status: Accepted
- Date: 2026-07-23

## Context

PlanGuard's query syntax, plan nodes, detectors, scenario dimensions, and extensions will grow.
Rejecting every unknown value makes old consumers brittle; silently ignoring unsupported analysis
makes results untrustworthy.

## Decision

- Artifact contracts and extension namespaces are registry-backed.
- Unknown namespaced extensions are preserved by default.
- Unknown core artifact contracts are rejected because their envelope semantics cannot be assumed.
- Unsupported or partial analytical behavior is represented through capability status and
  capability-gap artifacts.

## Consequences

Consumers can remain forward-tolerant for optional extensions while remaining strict about core
contracts and honest about unperformed analysis.
