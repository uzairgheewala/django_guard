# ADR 0001: Artifact-first semantic kernel

- Status: Accepted
- Date: 2026-07-23

## Context

PlanGuard will eventually capture query executions, derive multiple family projections, construct
workload graphs, collect PostgreSQL plans, evaluate policies, and execute generic scenarios. If
those subsystems exchange private in-memory objects, the CLI, API, UI, CI integration, and future
Pathforge orchestration will diverge.

## Decision

Every durable or cross-boundary result is a versioned artifact document with:

- stable artifact kind and schema version;
- event-like artifact ID;
- producer identity;
- explicit provenance;
- typed payload;
- namespaced extension payloads;
- SHA-256 over canonical JSON excluding the hash field itself.

JSON artifacts are canonical. Search indexes and UI projections are rebuildable derivatives.

## Consequences

- Schema design occurs before subsystem implementation.
- The UI cannot invent semantic state that is absent from artifacts.
- Unknown extensions can survive older consumers.
- Schema migrations and compatibility tests become mandatory.
- Artifacts are somewhat more verbose, but reproducibility and inspectability improve.
