# PlanGuard Workbench API

Milestone G adds benchmark, security, plugin, demonstration-case, and release resources while retaining all capture, workload, scenario, plan, comparison, universe, and counterexample APIs.

```text
GET  /api/v1/benchmarks/protocols
GET  /api/v1/benchmarks/series
POST /api/v1/benchmarks/run
GET  /api/v1/benchmarks/series/{series_id}

POST /api/v1/security/audit
POST /api/v1/security/sanitize
POST /api/v1/security/trust

GET  /api/v1/plugins
GET  /api/v1/demonstrations
GET  /api/v1/releases
POST /api/v1/releases/build
```

Artifact imports are size-limited, validated before indexing, and quarantined when malformed or over policy limits. Execution-capable benchmark and laboratory operations remain capability-gated. Canonical JSON artifacts remain the source of truth; SQLite is only a rebuildable query projection.
