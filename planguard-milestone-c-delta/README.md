# PlanGuard — Milestone C

Milestone C turns the developer MVP into a local visual analysis product:

```text
immutable run artifacts
  → rebuildable metadata index
  → search and provenance traversal
  → workload graph
  → reusable motif definitions
  → episode matches
  → synchronized timeline / family / graph workbench
```

Milestone C preserves Milestone A and B artifact semantics. New graph, motif, and episode
artifacts extend the union without changing previously persisted v1 documents.

## Implemented capabilities

### Indexed artifact workbench

- disposable SQLite projection over canonical JSON artifacts;
- explicit index rebuild and startup synchronization;
- search by text, artifact kind, run, tag, status, mode, mechanism, severity, or motif;
- paginated API responses;
- bidirectional provenance traversal;
- registry statistics;
- portable run-bundle export;
- direct artifact-index updates on imports and policy evaluations.

### Workload graph

- operation, transaction, query execution, query family, finding, evidence, and episode node kinds;
- observed, deterministically derived, and inferred edge classes;
- temporal, membership, containment, transaction, repetition, finding-subject, and possible-result-driving relationships;
- explicit confidence and evidence on inferred edges;
- alternate graph projections under any existing query-family scheme without recapture.

### Motifs and episodes

Built-in generic motifs:

- `exact-duplicate-cluster.v1`;
- `parameterized-repetition.v1`;
- `parent-driven-repeated-lookup.v1`;
- `per-item-write-loop.v1`;
- `long-transaction-accumulation.v1`.

A motif is a reusable structural definition. A workload episode is one match of that motif. Neither
is automatically a finding.

### Workbench UI

- dynamic registry home screen;
- filtered run and artifact browsers;
- synchronized workload graph, timeline, and family selection;
- family-lens graph regeneration;
- confidence filtering and inferred-edge controls;
- episode inspector;
- reusable motif catalog;
- bidirectional artifact provenance;
- local registry rebuild;
- portable run export.

The complete sample is `run_demo_c_001`.

## Install

```bash
python -m pip install -e .
python -m pip install -e '.[api]'
python -m pip install -e '.[dev]'
```

## Capture

```python
from planguard import profile

with profile("student-plan-detail", store=".planguard") as session:
    response = client.get("/students/18291/plan/")

print(session.manifest.artifact_id)
print(len(session.analysis.workload_episodes))
```

A deterministic laboratory adapter may supply an explicit `run_id` and call
`session.record_query(...)` directly.

## CLI

```bash
planguard inspect run_demo_c_001 --store examples/store
planguard index-rebuild --store examples/store
planguard search fanout --store examples/store --kind workload_episode
planguard export-run run_demo_c_001 --store examples/store
planguard report run_demo_c_001 --store examples/store --format html --output report.html
```

## Workbench

```bash
PLANGUARD_STORE=examples/store python services/workbench_api/manage.py runserver

cd apps/workbench-ui
npm install
npm run dev
```

Primary surfaces:

- `/` — live registry summary and recent runs;
- `/runs` — indexed run search;
- `/runs/{run_id}` — synchronized graph, timeline, families, findings, receipts, and policies;
- `/motifs` — reusable motif definitions and match counts;
- `/artifacts` — indexed artifact search and import;
- `/artifacts/{artifact_id}` — payload, integrity, and bidirectional provenance;
- `/policies` — policy creation and evaluation;
- `/capabilities` — capability and contract inventory.

## Contracts

Milestone C adds:

```text
planguard.workload-graph.v1
planguard.workload-motif.v1
planguard.workload-episode.v1
```

Regenerate contracts with:

```bash
make contracts
```

## Samples and tests

```bash
make seed
pytest
```

The committed sample store contains Milestone A, B, and C runs. The SQLite registry is deliberately
not canonical and may be deleted; the API or `planguard index-rebuild` reconstructs it.

## Safety and epistemic boundary

Milestone C does not execute arbitrary SQL, collect PostgreSQL plans, rewrite ORM code, or create
indexes. An inferred graph edge is never rendered as observed fact. Motif occurrence is never
silently promoted to a performance defect. The workbench always links claims back to immutable
artifacts.

## Milestone C validation snapshot

```text
25 tests passed
3 optional suites skipped (Django/Hypothesis unavailable)
128/128 sample artifacts verified
15 TypeScript/TSX sources transpiled without syntax diagnostics
portable run export verified
```
