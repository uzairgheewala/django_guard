# ADR 0004: Generated JSON Schema and TypeScript contract boundary

- Status: Accepted
- Date: 2026-07-23

## Context

The workbench UI must not manually duplicate Python artifact interfaces.

## Decision

Pydantic models generate:

- per-artifact JSON Schema;
- a discriminated `AnyArtifact` JSON Schema;
- TypeScript interfaces consumed by the React application.

A contract test regenerates outputs and compares them byte-for-byte with committed files.

## Consequences

A Python contract change that is not propagated to the UI fails tests. The initial TypeScript
converter deliberately supports the JSON Schema subset emitted by Milestone A and must evolve with
new schema constructs.
