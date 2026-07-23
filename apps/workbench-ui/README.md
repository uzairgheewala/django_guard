# PlanGuard Workbench UI

Milestone D adds Scenario Studio at `/scenarios`. It consumes canonical template, binding, mutation,
instance, dataset, receipt, and scenario-run contracts from the workbench API. No scenario semantics
are duplicated as frontend-only state: every runnable configuration is serializable to the same
instance payload used by the CLI and Python runner.

```bash
npm install
npm run dev
```

Set `VITE_PLANGUARD_API_BASE` when the API is not at `http://127.0.0.1:8000`.
