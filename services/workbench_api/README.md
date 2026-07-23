# PlanGuard Workbench API

Milestone E adds PostgreSQL plan and comparison resources:

```text
GET  /api/v1/runs/{run_id}/plans
POST /api/v1/runs/{run_id}/plans/import
POST /api/v1/runs/{run_id}/plans/collect
GET  /api/v1/plans/{plan_id}
GET  /api/v1/comparisons
POST /api/v1/comparisons/create
GET  /api/v1/comparisons/{comparison_id}
```

Imported plan analysis is always available. Live database plan collection is disabled unless `PLANGUARD_PLAN_EXECUTION_ENABLED=1`; `EXPLAIN ANALYZE` is additionally constrained by the submitted collection policy and statement safety checks.
