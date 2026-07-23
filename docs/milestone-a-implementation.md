# Milestone A implementation record

## Scope delivered

Milestone A combines implementation-plan Phases 0 and 1:

1. repository and development scaffolding;
2. canonical artifact envelope;
3. deterministic JSON serialization and SHA-256 sealing;
4. artifact references and provenance;
5. explicit capability status and capability-gap artifacts;
6. open artifact and extension registries;
7. run-manifest, environment-profile, and capture-policy contracts;
8. immutable content-addressed filesystem store;
9. JSON Schema and TypeScript contract generation;
10. Django workbench API shell;
11. React Artifact Inspector shell;
12. sample store and contract, integrity, registry, and persistence tests.

## Deliberately deferred

The following are represented as unsupported capabilities, not empty successful analyses:

- Django SQL capture;
- query normalization and family schemes;
- findings and policy evaluation;
- workload graphs;
- scenario execution;
- PostgreSQL plans;
- universe generation and coverage.

## Invariants established

- Artifact IDs are immutable pointers to one content hash.
- Canonical object content is immutable and content-addressed.
- Every artifact has a declared producer, schema version, and provenance object.
- Every persisted artifact must be sealed and integrity-verifiable.
- Unknown extension namespaces survive decode/encode cycles.
- Unknown core artifact contracts are rejected.
- Generated frontend contracts are byte-for-byte reproducible from Python models.
- Search indexes are rebuildable and never authoritative.

## Acceptance evidence

Core validation in the construction environment:

- Python compile check passed.
- Editable package installation passed.
- CLI validation and store listing passed.
- Four sample artifact pointers and four content-addressed objects verify.
- 15 available tests passed.
- Django API integration test was present but skipped because Django was not installed in the
  construction environment.
- Hypothesis property suite was present but skipped because Hypothesis was not installed in the
  construction environment.
- TypeScript application sources passed an isolated compiler consistency check using temporary
  module declarations; an npm/Vite production build could not be run without installed npm
  dependencies.
