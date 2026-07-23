# PlanGuard architecture

PlanGuard separates runtime events, immutable evidence, derived analysis, user interfaces, and extension contracts.

```text
instrumented Django/PostgreSQL operation
  → scoped capture runtime
  → immutable query-execution artifacts
  → normalization and explicit family schemes
  → workload graph, motifs, findings, and policies
  → scenario and plan experiments
  → comparisons and declared-universe coverage
  → benchmark, security, and release artifacts
```

The filesystem artifact store is canonical. The SQLite registry is rebuildable. UI state is never the only representation of a policy, scenario, universe, benchmark, plugin, or release.

## Epistemic separation

Observed events, deterministic derivations, inferred relationships, detector claims, and unsupported analyses are represented separately. A workload motif is not automatically a pathology; a timing delta is not automatically causal; a new plugin is not automatically trusted.

## Extension boundary

Plugins exchange versioned artifacts and declared capabilities. PlanGuard core does not import application-specific Pathforge code. Scenario adapters, stores, detectors, reporters, motifs, plan extractors, and coverage strategies remain replaceable behind contracts.
