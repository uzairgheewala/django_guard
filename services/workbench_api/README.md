# PlanGuard Workbench API — Milestone B

The Django service indexes and serves the immutable artifact store. It does not own PlanGuard's
semantic state.

## Run

```bash
PLANGUARD_STORE=examples/store python services/workbench_api/manage.py runserver
```

## Endpoints

- `GET /api/v1/health`
- `GET /api/v1/capabilities`
- `GET /api/v1/artifacts`
- `GET /api/v1/artifacts/{artifact_id}`
- `GET /api/v1/artifacts/{artifact_id}/integrity`
- `POST /api/v1/import`
- `GET /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/families?scheme=shape-origin.v1`
- `GET /api/v1/runs/{run_id}/findings`
- `POST /api/v1/runs/{run_id}/policy-evaluations`

Policy evaluation accepts either `policy_artifact_id`, a sealed `policy`, or an unsealed
`policy_payload` that the API seals and persists before evaluation.
