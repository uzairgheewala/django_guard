# PlanGuard Workbench API

The local Django API indexes immutable PlanGuard artifacts and exposes run, workload, policy, and
scenario resources. Milestone D adds:

```text
GET  /api/v1/scenarios/catalog
POST /api/v1/scenarios/instances
GET  /api/v1/scenarios/runs
POST /api/v1/scenarios/run
GET  /api/v1/scenarios/runs/{scenario_run_id}
```

Scenario execution is disabled unless `PLANGUARD_LAB_ENABLED=1`. Local debug mode enables the
built-in deterministic academic adapter by default; production-like deployments default it off.
