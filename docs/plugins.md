# Plugin contracts

PlanGuard discovers third-party extensions through the `planguard.plugins` entry-point group. An entry point returns a `PluginManifestArtifact` or a `(manifest, component)` pair.

A manifest declares component type, accepted and emitted schema versions, capability requirements, determinism, configuration schema, and safety profile. Duplicate plugin keys fail. Enabled plugins with missing required capabilities fail. Discovery success does not imply trust.

## Component types

- detector;
- reporter;
- family dimension;
- selector operator;
- workload motif;
- plan extractor;
- scenario adapter;
- mutation;
- artifact store;
- coverage strategy.

Plugin execution can be wrapped in a timeout contract. Strong isolation for untrusted code still requires an external process or container and is outside the in-process plugin manager's guarantee.
