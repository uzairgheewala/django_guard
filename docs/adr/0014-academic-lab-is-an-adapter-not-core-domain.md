# ADR 0014: The academic laboratory is an adapter, not a core domain

## Status
Accepted for Milestone D.

## Decision
Academic entities, distributions, and operations live under `planguard.lab.academic` and the optional
Django app. Core scenario contracts refer only to generic roles, domains, variants, mutations,
oracles, and adapter keys.

## Consequences
The laboratory is realistic enough to prepare for academic SaaS work while the scenario system can
later bind to commerce, observability, integration, or Pathforge workloads without schema changes.
