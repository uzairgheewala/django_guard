# PlanGuard — Milestone B

Milestone B delivers the first complete developer MVP for PlanGuard:

```text
scoped capture
  → immutable query executions
  → conservative SQL templates
  → explicit family schemes
  → evidence and detector receipts
  → findings
  → absolute budgets
  → pytest / CLI / API / workbench reports
```

It extends Milestone A without changing the meaning of the existing v1 artifact contracts.

## Implemented capabilities

- scoped manual and Django `execute_wrapper` capture;
- context-local run lifecycle and multiple database aliases;
- safe SQL modes and parameter shape/HMAC capture;
- configurable application-origin capture;
- query-execution, query-template, family-scheme, observed-family, evidence, finding,
  detector-receipt, budget-policy, budget-evaluation, and analysis-summary artifacts;
- deterministic conservative SQL normalization with explicit parse quality;
- four family lenses:
  - `exact-execution.v1`;
  - `structural-shape.v1`;
  - `shape-origin.v1`;
  - `shape-parameter-regime.v1`;
- four initial detectors:
  - exact duplicate execution;
  - structural repetition;
  - likely N+1;
  - database-time concentration;
- generic selector and absolute policy engine;
- pytest marker and explicit `plan_guard` fixture;
- terminal, JSON, and standalone HTML reporting;
- run/family/finding/policy workbench API endpoints;
- Runs, Run Explorer, family-lens explorer, finding views, and Policy Studio UI;
- a complete sample run at `run_demo_b_001`.

PostgreSQL plan collection, workload graphs, generic scenarios, comparisons, and universe
coverage remain explicit later-milestone capabilities.

## Install

Core and CLI:

```bash
python -m pip install -e .
```

Django API and capture integration:

```bash
python -m pip install -e '.[api]'
```

Development and pytest integration:

```bash
python -m pip install -e '.[dev]'
```

## Capture an operation

```python
from planguard import QueryPolicy, profile

with profile(
    "student-plan-detail",
    store=".planguard",
    budget_policy=QueryPolicy(
        max_queries=12,
        max_family_executions=4,
        forbid_findings=frozenset({"likely-n-plus-one.v1"}),
    ),
) as session:
    response = client.get("/students/18291/plan/")

print(session.manifest.artifact_id)
print(session.analysis.summary.payload.query_count)
```

The Django adapter is attached automatically when Django is installed and configured. For
framework-independent tests or scenario adapters, `session.record_query(...)` records the same
canonical evidence manually.

## Pytest

Automatic marker capture:

```python
import pytest

@pytest.mark.planguard(
    max_queries=12,
    max_family_executions=4,
    forbid_findings=("likely-n-plus-one.v1",),
)
def test_student_plan(client):
    assert client.get("/students/18291/plan/").status_code == 200
```

Explicit fixture capture:

```python
def test_student_plan(client, plan_guard):
    with plan_guard.capture(name="student-plan", policy=QueryPolicy(max_queries=12)):
        assert client.get("/students/18291/plan/").status_code == 200
```

Artifacts are written to `.planguard` by default. Override with `--planguard-store PATH`.

## CLI

```bash
planguard inspect run_demo_b_001 --store examples/store
planguard report run_demo_b_001 --store examples/store --format html --output report.html
planguard policy-evaluate run_demo_b_001 policy.json --store examples/store --persist
planguard list --store examples/store --kind finding
planguard verify --store examples/store
```

## Workbench

API:

```bash
PLANGUARD_STORE=examples/store python services/workbench_api/manage.py runserver
```

UI:

```bash
cd apps/workbench-ui
npm install
npm run dev
```

The workbench exposes:

- `/runs` — captured runs;
- `/runs/{run_id}` — timeline, family lenses, findings, receipts, and evaluations;
- `/policies` — structured absolute-budget creation and evaluation;
- `/artifacts` — canonical artifact registry and inspector;
- `/capabilities` — supported, partial, and deferred capabilities.

## Samples and contracts

```bash
make contracts
make seed
pytest
```

`make seed` retains the Milestone A semantic-foundation sample and adds the Milestone B query
analysis sample.

## Safety boundary

Milestone B does not execute arbitrary SQL, rewrite ORM code, create indexes, or collect
PostgreSQL plans. Raw SQL is redacted and parameter values are represented by shape and HMAC by
default. Detector claims expose confidence and limitations; repetition is never treated as proof
of avoidability.
