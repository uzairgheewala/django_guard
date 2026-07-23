# PlanGuard — Milestone D

Milestone D adds the generic experiment layer above the Milestone C visual workload workbench:

```text
scenario template
  → application binding
  → deterministic instance
  → ordered mutations
  → receipt-bearing execution
  → captured query workload
  → oracle evaluations
  → linked Scenario Studio and Run Explorer
```

The academic laboratory is one binding environment. Scenario semantics remain domain-neutral in
`planguard.scenario`; no student, course, or university type appears in the core contracts.

## Delivered capabilities

### Generic scenario kernel

- versioned templates, roles, parameter domains, operation graphs, variants, oracles, and coverage obligations;
- explicit application bindings for roles and variants;
- deterministic scenario instances with content-derived identities;
- ordered application, schema, data, runtime, and workload mutations;
- scenario series and deterministic pairwise generation;
- `bind` validation, `instantiate`, `scale`, `contrast`, and pairwise covering operations;
- open registries for templates, bindings, mutations, and adapters;
- explicit unsupported and non-evaluated states.

### Receipt-bearing runner

Every execution materializes receipts for:

```text
prepare_environment
prepare_dataset
apply_mutations
execute_operation
evaluate_oracles
cleanup
```

A failed phase still yields a valid scenario run, failure receipt, cleanup receipt, provenance, and
any already-produced artifacts. The underlying `AnalysisSession` run records the
`scenario_instance_ref`, so the Scenario Studio and workload explorer traverse the same immutable
evidence graph.

### Deterministic academic laboratory

The built-in `academic-lab.v1` adapter provides:

- shared-schema multi-tenant domain semantics;
- deterministic seed-controlled generation;
- tiny, small, medium, and large logical scale profiles;
- uniform, dominant-tenant, and Zipf-like distributions;
- dataset fingerprints and materialization manifests;
- tenant-isolation oracles;
- PostgreSQL-shaped query emission through the manual capture adapter;
- an optional Django model package under `apps/academic-lab` for future real ORM/PostgreSQL binding.

Generic templates are bound to ten academic operations:

1. relation access fan-out → plan items and courses;
2. nested relation fan-out → students, enrollments, and courses;
3. repeated evaluation → student plan collection;
4. count then fetch → advisor roster;
5. per-item check/write → transcript import;
6. per-item update → audit-status recalculation;
7. aggregate amplification → graduation-risk report;
8. offset pagination → course search;
9. tenant-skew sensitivity → institution dashboard;
10. long transaction accumulation → catalog update.

Built-in mutations include eager-loading removal, forced per-row writes, tenant-index removal,
tenant-skew amplification, expanded hydration, extended transaction scope, stale statistics, and
relation-fanout growth.

### Scenario Studio

The workbench adds `/scenarios` with:

- generic template selection;
- visible academic role binding;
- naïve and optimized variants;
- scale, skew, fan-out, batching, pagination, and transaction controls;
- ordered mutation selection;
- deterministic seed control;
- phase receipt timeline;
- oracle results;
- dataset-manifest links;
- direct navigation to the captured workload run and Artifact Inspector;
- recent scenario-run registry.

Laboratory execution is capability-gated by `PLANGUARD_LAB_ENABLED`. It defaults on only in local
Django debug mode.

## Install

```bash
python -m pip install -e .
python -m pip install -e '.[api]'
python -m pip install -e '.[dev]'
```

## Python usage

```python
from planguard.artifacts.models import ProducerIdentity
from planguard.lab.academic import build_academic_catalog
from planguard.scenario import ScenarioRunner, instantiate
from planguard.store.filesystem import FilesystemArtifactStore

producer = ProducerIdentity(name="planguard-demo", version="1")
catalog = build_academic_catalog(producer=producer)
store = FilesystemArtifactStore(".planguard")
catalog.persist(store)

template = catalog.registry.require_template("relation-access-fanout.v1")
binding = catalog.registry.require_binding("academic.plan-item-course.v1")
instance = instantiate(
    template,
    binding,
    parameters={"parent_count": 25, "tenant_skew": "dominant"},
    variant_key="optimized",
    seed=42,
    producer=producer,
)
result = ScenarioRunner(registry=catalog.registry, store=store, producer=producer).run(instance)
print(result.scenario_run.artifact_id)
print(result.captured_run.manifest.artifact_id)
```

## CLI

```bash
planguard scenario-catalog --store examples/store
planguard scenario-instantiate relation-access-fanout.v1 academic.plan-item-course.v1 \
  --variant naive --parameter parent_count=20 --seed 42 --store examples/store
planguard scenario-run --template relation-access-fanout.v1 \
  --binding academic.plan-item-course.v1 --variant optimized \
  --parameter parent_count=20 --mutation remove-eager-loading.v1 \
  --seed 42 --store examples/store
```

Existing capture, inspect, report, policy, index, search, and export commands remain available.

## Workbench

```bash
PLANGUARD_STORE=examples/store PLANGUARD_LAB_ENABLED=1 \
  python services/workbench_api/manage.py runserver

cd apps/workbench-ui
npm install
npm run dev
```

Primary surfaces now include:

- `/scenarios` — template, binding, instance, mutation, execution, receipt, and oracle workbench;
- `/runs/{run_id}` — the captured workload graph and query-family analysis linked from a scenario;
- `/artifacts/{artifact_id}` — canonical scenario, dataset, receipt, and run documents;
- all Milestone C run, motif, policy, registry, and capability screens.

## New contracts

```text
planguard.scenario-template.v1
planguard.scenario-binding.v1
planguard.scenario-instance.v1
planguard.scenario-series.v1
planguard.scenario-phase-receipt.v1
planguard.scenario-run.v1
planguard.dataset-manifest.v1
planguard.mutation-definition.v1
```

Regenerate JSON Schema and TypeScript contracts with `make contracts`.

## Seed and test

```bash
make seed
pytest
```

The committed sample store contains ten generic templates, ten academic bindings, eight mutation
definitions, representative naïve and optimized runs, a scale series, and a pairwise-generated
scenario set. The SQLite index remains disposable and rebuildable from canonical JSON artifacts.

## Safety and scope

Milestone D does not execute arbitrary SQL or alter a real schema. The built-in academic adapter is
a deterministic laboratory simulator. Real Django/PostgreSQL adapters must be registered
explicitly and remain subject to workbench capability gating. Scenario oracles report what was and
was not evaluated; a missing oracle is never silently considered satisfied.
