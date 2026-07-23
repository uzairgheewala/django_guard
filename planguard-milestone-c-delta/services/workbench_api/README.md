# PlanGuard Workbench API — Milestone C

Local Django API over immutable artifacts and a rebuildable SQLite metadata index.

```bash
PLANGUARD_STORE=examples/store python services/workbench_api/manage.py runserver
```

The service supports indexed artifact/run search, bidirectional provenance, graph and episode
projections, registry rebuilding, policy evaluation, and portable run export. Canonical JSON remains
the source of truth.
