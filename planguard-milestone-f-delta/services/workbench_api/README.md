# PlanGuard Workbench API

Milestone F adds declared-universe coverage and counterexample lifecycle resources while retaining all capture, workload, scenario, plan, and comparison endpoints.

```text
GET  /api/v1/universes/catalog
GET  /api/v1/universes/{universe_id}
POST /api/v1/universes/{universe_id}/representatives
POST /api/v1/universes/{universe_id}/coverage
GET  /api/v1/coverage-reports

POST /api/v1/runs/{run_id}/novelty
GET  /api/v1/counterexamples
POST /api/v1/counterexamples/create
POST /api/v1/counterexamples/{counterexample_id}/minimize
POST /api/v1/counterexamples/{counterexample_id}/promote
```

The API persists canonical universe, representative-set, coverage, novelty, counterexample, minimization, and promotion artifacts. The SQLite registry remains a rebuildable query projection and is never the source of truth.

Scenario execution and minimization require `PLANGUARD_LAB_ENABLED=1`. Coverage evaluation and read-only novelty analysis operate over stored artifacts without executing application code.
