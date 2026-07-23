# PlanGuard — Milestone G

PlanGuard is an artifact-first Django/PostgreSQL workload analysis, experiment, and regression platform. Milestone G completes the mature standalone OSS boundary: repeatable benchmark series, operational safety and sanitization, versioned plugin contracts, and a verified demonstration/release corpus.

```text
captured workload evidence
  → query families and workload motifs
  → PostgreSQL plans and semantic comparisons
  → generic scenarios and declared-universe coverage
  → repeated benchmark series
  → security audit and trust verification
  → versioned plugins and demonstration cases
  → immutable release manifest
```

Canonical JSON artifacts remain the source of truth. The SQLite workbench index is disposable, timing evidence is explicitly qualified by comparability, and an extension cannot silently invent new persisted semantics outside the versioned artifact boundary.

## Milestone G capabilities

### Reliable experiment series

`BenchmarkProtocolArtifact` declares:

- warm-up and measured iterations;
- cache-state protocol;
- randomization and deterministic seed;
- outlier policy;
- confidence level;
- dimension domains;
- concurrency levels;
- required environment fields;
- metrics and timeouts.

`ExperimentSeriesArtifact` retains every sample, including warm-ups, failed workers, exclusions, environment references, robust metric distributions, and conservative observed-scaling assessments. PlanGuard reports approximately constant, sublinear, approximately linear, superlinear, threshold-transition, or inconclusive behavior over the measured range. It does not claim formal Big-O complexity from a short benchmark.

The generic concurrency harness starts workers behind one barrier and records wall time, throughput, errors, timeouts, and adapter-provided lock/resource metrics.

### Artifact security and operational hardening

Milestone G adds:

- HMAC-safe capture defaults retained from earlier milestones;
- pattern-backed security audits;
- explicit findings for preserved SQL and parameter values;
- credential, bearer-token, email, payment-card, private-key, and path detection;
- schema-preserving sanitized derivative artifacts;
- sanitization receipts with exact redacted paths;
- content-hash and provenance-reference trust reports;
- invalid-import quarantine;
- import-size, audit-size, capture-size, and store-quota controls;
- explorer/laboratory and live-plan execution gates.

A clean scanner result does not prove that an artifact contains no sensitive information. The limitation is persisted in each security audit.

### Stable plugin contracts

Every extension is represented by a `PluginManifestArtifact` declaring:

- plugin key and version;
- Python package and entry point;
- component type;
- accepted and emitted artifact schemas;
- required capabilities;
- determinism class;
- configuration schema;
- safety profile;
- default enablement.

Built-in manifests cover detectors, PostgreSQL plan extractors, the academic scenario adapter, coverage strategies, the filesystem store, and reporters. Third-party entry points use the `planguard.plugins` group. Duplicate keys and unavailable required capabilities fail explicitly. Optional execution is bounded by a timeout contract.

### Demonstration corpus and releases

A `DemonstrationCaseArtifact` binds one reusable case to:

- generic scenario template;
- application binding;
- baseline and candidate runs when available;
- semantic comparison;
- policies;
- benchmark series;
- case documentation;
- expected mechanisms.

A `ReleaseManifestArtifact` binds package version, all artifact schema versions, plugin contract version, demonstration cases, security/trust evidence, compatibility, checksums, documentation, and validation results into one immutable release candidate.

Eight documented academic bindings are seeded:

1. relation fan-out;
2. nested fan-out;
3. repeated evaluation;
4. count then fetch;
5. per-item check/write;
6. aggregate-report amplification;
7. offset-pagination degradation;
8. tenant-skew sensitivity.

### Workbench UI

New surfaces:

- `/benchmarks` — protocols, repeated series, robust distributions, and observed scaling;
- `/security` — audits, trust checks, and schema-preserving sanitization;
- `/plugins` — built-in and discovered plugin contracts;
- `/release` — demonstration verification and release-manifest construction.

All prior run, family, workload-graph, scenario, plan, comparison, universe, detector, policy, artifact, and capability surfaces remain available.

## Install

```bash
python -m pip install -e .
python -m pip install -e '.[api]'
python -m pip install -e '.[dev]'
```

## Core CLI workflows

```bash
# Benchmark protocols and a repeated series
planguard benchmark-catalog --store examples/store
planguard benchmark-run BENCHMARK_PROTOCOL_ID \
  --metric-model linear \
  --store examples/store \
  --persist

# Security and trust
planguard security-audit --all --store examples/store --persist
planguard sanitize-artifact ARTIFACT_ID --store examples/store --persist
planguard trust-verify --all --store examples/store --persist

# Plugin contracts
planguard plugin-list --discover --store examples/store --persist

# Demonstration and release verification
planguard demo-verify --store examples/store
planguard release-build \
  --release-key planguard-0.7.0 \
  --status candidate \
  --store examples/store \
  --persist
```

All previous capture, query-family, policy, workload, scenario, plan, comparison, universe, novelty, and counterexample commands remain available.

## Workbench

```bash
PLANGUARD_STORE=examples/store \
PLANGUARD_LAB_ENABLED=1 \
PLANGUARD_PLAN_EXECUTION_ENABLED=0 \
python services/workbench_api/manage.py runserver

cd apps/workbench-ui
npm install
npm run dev
```

Invalid imports are quarantined beneath the configured `PLANGUARD_QUARANTINE` directory. Live PostgreSQL plan execution remains disabled unless explicitly enabled.

## New Milestone G contracts

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

Regenerate JSON Schema and TypeScript contracts with:

```bash
make contracts
```

## Seed and test

```bash
make seed
pytest
```

The Milestone G seed adds benchmark protocols and series, plugin manifests, a deliberately unsafe capture-policy sample and its sanitized derivative, a security audit, a trust report, eight demonstration cases, and one verified release manifest.

## Documentation

- [Architecture](docs/architecture.md)
- [Benchmark methodology](docs/benchmarking.md)
- [Security and redaction](docs/security.md)
- [Plugin contracts](docs/plugins.md)
- [Artifact schema policy](docs/artifact-schemas.md)
- [Milestone G implementation record](docs/milestone-g-implementation.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Contributing guide](CONTRIBUTING.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Apache 2.0 license](LICENSE)
- [Changelog](CHANGELOG.md)

## Scope and honesty

- performance timing is advisory when environment comparability is degraded;
- observed scaling is not a proof of asymptotic complexity;
- scanner coverage cannot prove the absence of sensitive information;
- sanitization creates a new derivative and never mutates the original artifact;
- unknown plugin schemas and capabilities remain explicit;
- third-party plugins are not trusted merely because discovery succeeds;
- no ORM/SQL rewriting or automatic index creation is introduced;
- Pathforge integration remains a later adapter boundary rather than a PlanGuard core dependency.
