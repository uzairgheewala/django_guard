# PlanGuard — Milestone E

Milestone E adds safe PostgreSQL plan intelligence and comparability-first optimization analysis on top of the Milestone D generic scenario laboratory.

```text
captured query family
  → representative parameter regime
  → safety policy
  → EXPLAIN / authorized EXPLAIN ANALYZE
  → canonical plan tree and features
  → evidence-backed plan findings
  → baseline/candidate comparability assessment
  → workload, family, plan, finding, and resource diffs
  → relative regression policy
```

The source of truth remains immutable, versioned JSON artifacts. PostgreSQL plans and comparisons are not frontend-only views, and the SQLite workbench index remains disposable.

## Milestone E capabilities

### PostgreSQL plan engine

- safe collection policies: `disabled`, `estimated_only`, `analyze_safe_selects`, `explicit_allowlist`, and `imported`;
- explicit statement timeout and read-only/volatile-shape checks before `EXPLAIN ANALYZE`;
- imported `FORMAT JSON` plans for offline analysis and CI fixtures;
- canonical plan nodes with relation, index, join, estimates, actuals, loops, buffers, temporary I/O, memory, filters, and unknown-attribute preservation;
- stable semantic plan-shape fingerprints;
- parameter-regime and representative-execution provenance;
- collection receipts for collected, rejected, failed, skipped, and capability-missing attempts;
- contextual findings for high-volume sequential scans, cardinality misestimation, disk spills, and nested-loop multiplication.

Plan operators are never treated as inherently bad. Findings carry evidence, confidence, limitations, and conservative remediation guidance.

### Comparison engine

Every comparison assesses these dimensions before interpreting deltas:

- scenario template and binding;
- scenario parameters and deterministic seed;
- implementation variant;
- environment profile;
- capture policy.

Each dimension is classified as:

```text
identical
compatible
controlled_change
confounding_change
unknown
```

The overall comparison becomes `valid`, `valid_with_controlled_changes`, `degraded`, or `invalid`. Structural and plan comparisons can remain useful when timing evidence is merely advisory.

Comparison reports include:

- query, template, family, finding, and database-time deltas;
- query-family added/removed/changed/split/merged classifications;
- semantic plan transitions such as `Seq Scan → Index Scan`;
- index-set, buffer, temporary-I/O, and actual-execution-time deltas;
- introduced and resolved finding mechanisms;
- relative policy evaluations;
- a provenance-linked evidence narrative and limitations.

### Workbench UI

New surfaces:

- `/plans/{plan_id}` — canonical plan tree, actual-versus-estimated metrics, resource features, and raw plan JSON;
- `/comparisons` — select baseline and candidate runs and create a persisted report;
- `/comparisons/{comparison_id}` — comparability dimensions, metrics, family changes, plan transitions, and policy results;
- the Run Explorer now has a Plans tab linked to the same canonical plan artifacts.

Existing Scenario Studio, workload graph, query-family, motif, policy, artifact, and capability surfaces remain available.

## Install

```bash
python -m pip install -e .
python -m pip install -e '.[api]'
python -m pip install -e '.[dev]'
```

## Imported-plan usage

```python
import json

from planguard.artifacts.models import ProducerIdentity
from planguard.postgres import analyze_plan, import_plan

plan, receipt = import_plan(
    raw_plan=json.loads(open("plan.json").read()),
    run_id="run_example",
    query_family_ref=family.reference(),
    producer=ProducerIdentity(name="demo", version="1"),
)
evidence, findings = analyze_plan(
    plan,
    producer=ProducerIdentity(name="demo", version="1"),
    high_volume_relations=frozenset({"enrollment"}),
)
```

## Safe live collection

```python
from planguard.artifacts.models import PlanCollectionMode, ProducerIdentity
from planguard.postgres import PlanCollectionPolicy, collect_plan

plan, receipt = collect_plan(
    connection=django_connection,
    sql="SELECT * FROM enrollment WHERE student_id = %s",
    params=[17],
    run_id=run_id,
    query_family_ref=family.reference(),
    producer=ProducerIdentity(name="demo", version="1"),
    policy=PlanCollectionPolicy(
        mode=PlanCollectionMode.ESTIMATED_ONLY,
        statement_timeout_ms=2_000,
    ),
)
```

`EXPLAIN ANALYZE` remains opt-in. The workbench endpoint that executes plans is disabled unless `PLANGUARD_PLAN_EXECUTION_ENABLED=1`.

## CLI

```bash
planguard plan-import RUN_ID FAMILY_ID plan.json --store examples/store --persist
planguard compare BASELINE_RUN_ID CANDIDATE_RUN_ID --store examples/store --persist
```

All prior capture, inspect, report, policy, search, export, and scenario commands remain available.

## Workbench

```bash
PLANGUARD_STORE=examples/store \
PLANGUARD_LAB_ENABLED=1 \
PLANGUARD_PLAN_EXECUTION_ENABLED=0 \
python services/workbench_api/manage.py runserver

cd apps/workbench-ui
npm install
npm run dev
```

## New contracts

```text
planguard.plan-observation.v1
planguard.plan-collection-receipt.v1
planguard.comparison-report.v1
```

Regenerate JSON Schema and TypeScript contracts with:

```bash
make contracts
```

## Seed and test

```bash
make seed
pytest
```

The Milestone E seed creates a naïve and optimized relation-fan-out pair with the same template, binding, parameters, and deterministic seed. It imports representative analyzed-format sequential-scan and index-scan fixtures without executing SQL, persists explicit import receipts, and creates a `valid_with_controlled_changes` comparison protected by a relative query-count policy.

## Safety and scope

- no ORM or SQL rewriting;
- no automatic index creation;
- no arbitrary query execution from imported artifacts;
- `EXPLAIN ANALYZE` requires an execution-enabled workbench and a safety policy;
- write-shaped and volatile-looking statements are rejected for analysis by default;
- timing evidence is downgraded when environment comparability is incomplete;
- raw plans preserve unknown PostgreSQL fields instead of silently discarding unsupported semantics.
