# Milestone C implementation record

## Scope

Milestone C implements Phases 6 and 7 of the PlanGuard roadmap: the indexed local workbench and the
workload graph/episode layer.

## Semantic additions

### `planguard.workload-graph.v1`

A graph is one run-specific projection under an explicit family scheme. It contains typed nodes and
edges, and every edge declares an inference method:

- `observed` — directly represented by capture evidence;
- `derived` — deterministic aggregation or membership;
- `inferred` — a causal hypothesis carrying confidence, method, and evidence.

The graph validator rejects duplicate node/edge IDs and dangling edges.

### `planguard.workload-motif.v1`

A motif is a reusable structural pattern defined independently of any academic model. It declares
roles, admissible node/edge kinds, constraints, and associated mechanism keys.

### `planguard.workload-episode.v1`

An episode is a run-specific motif occurrence with role bindings, constraint evaluations, match
confidence, subject references, and provenance.

## Workload builder

`planguard.analysis.workload.build_workload(...)`:

1. chooses one explicit family scheme;
2. creates operation, execution, transaction, family, and finding nodes;
3. adds observed and derived containment/membership/temporal edges;
4. conservatively infers possible result-driving edges from temporal and cardinality alignment;
5. emits a canonical graph artifact;
6. evaluates reusable motif definitions;
7. emits episode artifacts without converting them into findings.

Alternate family lenses can be built from a persisted run without recapturing SQL.

## Rebuildable index

`ArtifactIndex` is a SQLite projection with:

- artifact metadata;
- run context;
- finding and motif facets;
- tags;
- provenance edges;
- text search;
- pagination;
- registry statistics.

Canonical JSON remains authoritative. The database may be removed and rebuilt at any point.

## API additions

```text
GET  /api/v1/registry/stats
POST /api/v1/registry/rebuild
GET  /api/v1/artifacts/{artifact_id}/related
GET  /api/v1/runs/{run_id}/graph
GET  /api/v1/runs/{run_id}/episodes
GET  /api/v1/runs/{run_id}/export
GET  /api/v1/motifs
```

Artifact and run list endpoints now support indexed filters and pagination.

## UI additions

- indexed home and recent-run view;
- run and artifact filter bars;
- workload SVG explorer;
- confidence threshold and inference toggles;
- synchronized graph/timeline/family selection;
- episode list and motif catalog;
- bidirectional provenance;
- portable bundle export.

## Validation

The implementation includes tests for:

- graph referential integrity;
- observed/derived/inferred separation;
- parent-driven lookup matching;
- repeated write matching;
- alternate family-lens projection;
- index rebuild, search, tags, statistics, and bidirectional provenance;
- all existing Milestone A/B contracts and behaviors.

## Completed validation

- `25` tests passed.
- `3` optional suites were skipped because Django and Hypothesis were not installed in the offline construction environment:
  - Django workbench API integration;
  - Django execution-wrapper capture;
  - Hypothesis artifact-property tests.
- Python compilation passed for packages, services, scripts, and tests.
- Generated JSON Schema and TypeScript contracts reproduced byte-for-byte.
- All `128` artifacts in the combined sample store passed content-hash and pointer integrity checks.
- The disposable SQLite index rebuilt all `128` artifacts and exposed workload motif and episode facets.
- CLI inspection, indexed search, registry rebuilding, and portable run export passed.
- The exported run ZIP passed archive integrity verification.
- All `15` frontend TypeScript/TSX sources passed syntax transpilation with the global TypeScript compiler.
- A full Vite production build was not available because npm dependencies could not be installed in the offline construction environment.
