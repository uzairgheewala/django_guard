# ADR 0002: Filesystem content-addressed store for Milestone A

- Status: Accepted
- Date: 2026-07-23

## Context

Milestone A needs immutable persistence, integrity verification, imports, and a sample workbench,
but does not yet need a service database or distributed object store.

## Decision

Use a filesystem-backed store with:

- canonical objects under `objects/sha256/<prefix>/<digest>.json`;
- immutable artifact-ID documents under `artifacts/<artifact_id>.json`;
- rebuildable metadata records under `index/`;
- atomic writes and collision checks.

## Consequences

- Local use and tests require no infrastructure.
- An artifact ID cannot be repointed to different content.
- Later stores must preserve the same `ArtifactStore` semantics.
- The index is intentionally not authoritative.
