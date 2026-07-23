# PlanGuard Workbench UI

Milestone E adds Plan Explorer and Comparison Workbench while retaining Scenario Studio and all existing artifact/run views.

```text
/plans/:planId
/comparisons
/comparisons/:comparisonId
```

The UI consumes canonical plan and comparison artifacts. It does not infer scan transitions, comparability, or relative-policy outcomes in browser-only state.

```bash
npm install
npm run dev
```

Set `VITE_PLANGUARD_API_BASE` when the API is not at `http://127.0.0.1:8000`.
