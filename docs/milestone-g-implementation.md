# Milestone G implementation record

## Scope

Milestone G implements Phases 14–16 of the PlanGuard roadmap:

1. statistically responsible benchmark series and controlled concurrency experiments;
2. security, redaction, quarantine, trust, and operational hardening;
3. stable plugin contracts, packaging, documentation, demonstration cases, and release manifests.

It is an additive implementation over Milestone F. Earlier artifact schemas retain their meaning and remain readable.

## Benchmark architecture

`BenchmarkProtocolArtifact` declares the measurement contract before execution: dimensions, warm-ups, iterations, cache protocol, seed, ordering, timeout, outlier policy, confidence level, environment requirements, concurrency levels, and metrics. `ExperimentSeriesArtifact` retains every observation and exclusion, robust metric summaries, controlled dimensions, environment references, limitations, and observed-scaling assessments.

The runner separates warm-up from measured observations, preserves failed and timed-out samples, supports deterministic ordering, and can execute concurrent workers behind a common barrier. Scaling classification is deliberately descriptive over the measured range; it is not represented as formal asymptotic proof.

## Security architecture

The security scanner evaluates canonical artifact structures using explicit rule artifacts and emits typed findings with paths and risk levels. Sanitization never mutates the original: it creates a schema-valid derivative plus an immutable receipt that enumerates each changed path. Trust verification checks canonical content integrity and available provenance references while explicitly avoiding claims of cryptographic authorship.

Malformed or oversized imports can be quarantined outside the canonical store. Quotas bound import size, audit breadth, artifact-store growth, query capture volume, and plugin execution time. Explorer, laboratory, and live-plan capabilities remain separately gated.

## Plugin architecture

Every extension declares a `PluginManifestArtifact` before execution. The manifest specifies component type, contract version, package and entry point, accepted and emitted schema versions, required capabilities, determinism, configuration schema, safety profile, default enablement, and documentation metadata.

The manager rejects duplicate keys, blocks default-enabled plugins with unavailable capabilities, preserves discovery errors as explicit results, and exposes timeout-bounded execution. The timeout protects workflow responsiveness but is not represented as a process security sandbox. A complete external reporter example is included under `examples/plugins/sample-reporter`.

## OSS release corpus

Eight `DemonstrationCaseArtifact` instances bind reusable scenario templates to the academic adapter and link available baselines, candidates, comparisons, policies, benchmark series, expected mechanisms, and case documentation. `ReleaseManifestArtifact` binds the package version, all artifact schemas, plugin contract, demonstration cases, checksums, documentation, compatibility, validation summary, security audit, and trust report into one immutable release record.

## Workbench additions

- `/benchmarks`: protocol catalog, execution controls, sample distributions, and observed scaling.
- `/security`: audit, sanitization, trust, quarantine, and risk explanation.
- `/plugins`: manifest contracts, capability requirements, determinism, and discovery state.
- `/release`: demonstration-case verification and release-manifest construction.

All workbench actions invoke the same canonical services used by the CLI. No benchmark conclusion, security decision, plugin contract, or release state exists only in browser state.

## New artifact contracts

```text
planguard.benchmark-protocol.v1
planguard.experiment-series.v1
planguard.security-audit.v1
planguard.artifact-sanitization.v1
planguard.artifact-trust-report.v1
planguard.plugin-manifest.v1
planguard.demonstration-case.v1
planguard.release-manifest.v1
```

## Upgrade application

The Milestone G archive contains only new or modified files. Overlay it on the Milestone F repository root. No repository paths are deleted by this milestone. The SQLite workbench index, local caches, build outputs, and package-manager dependency directories are intentionally excluded because they are disposable.

## Validation

Final release validation is recorded in the delivered release manifest and summarized in the accompanying response. It covers Python tests, compilation, contract regeneration, canonical-store integrity, registry rebuilding, CLI workflows, TypeScript/TSX transpilation, package construction, delta reconstruction, and archive checksums.

## Known environment limitations

The construction environment does not provide optional Django, Hypothesis, or installed frontend dependencies. Their integration/property suites or full Vite bundle therefore remain skipped or unexecuted locally, while committed CI installs those dependencies and runs the complete matrix.

## Final validation results

- 52 Python tests passed.
- 3 optional suites were skipped because Django and Hypothesis were unavailable in the construction environment.
- Python compilation succeeded across packages, services, scripts, and tests.
- Contract verification regenerated all JSON Schema and TypeScript contracts byte-for-byte.
- 26 TypeScript/TSX source files transpiled without syntax diagnostics.
- A full Vite bundle was not produced because frontend dependencies could not be installed in the offline environment.
- The canonical sample store contains 1,388 artifacts and all passed pointer/content-hash integrity verification.
- The disposable SQLite registry rebuilt all 1,388 canonical artifacts.
- All eight demonstration cases resolved every required reference.
- Benchmark, sanitization, trust, plugin-discovery, demonstration, and release CLI workflows completed against an isolated store copy.
- The deliberately unsafe sample correctly produced four security findings and a nonzero audit exit status.
- The primary `planguard` wheel and external sample-plugin wheel both built successfully; the primary wheel includes `py.typed`.
