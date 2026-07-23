# Milestone E implementation record

Milestone E implements Phases 10 and 11: PostgreSQL plan intelligence and defensible optimization comparison.

## Core implementation

### Artifact contracts

Added:

- `PlanObservationArtifact`;
- `PlanCollectionReceiptArtifact`;
- `ComparisonReportArtifact`.

The canonical plan model stores a validated tree, common execution and resource features, plan-shape fingerprint, raw plan document, collection context, representative query-family provenance, warnings, and capability gaps.

The comparison model stores dimension-level comparability, metric deltas, family changes, plan changes, finding changes, relative policy evaluations, narrative, and limitations.

### Plan normalization

`planguard.postgres.normalize` accepts PostgreSQL's one-element `FORMAT JSON` array, a top-level object containing `Plan`, or a direct plan root. It normalizes known fields while preserving unknown attributes. Feature extraction covers:

- plan topology and depth;
- operator counts;
- relation access methods;
- indexes;
- estimate error;
- nested-loop effective rows;
- rows removed by filters;
- shared hits and reads;
- temporary I/O and disk spill;
- parallelism;
- planning and execution time.

### Safe collection

`PlanCollectionPolicy` separates estimated-only collection from analyzed execution. `collect_plan` rejects disabled, non-PostgreSQL, mutating, non-allowlisted, and volatile-looking analysis requests before executing them. Every attempt returns a receipt, including rejection and failure paths.

### Plan findings

Initial plan detectors produce normal `EvidenceArtifact` and `FindingArtifact` documents for:

- high-volume sequential scans;
- cardinality misestimation;
- sort/hash disk spill;
- nested-loop multiplication.

### Comparison engine

`compare_runs` evaluates comparability before calculating:

- run metrics;
- family additions, removals, changes, splits, and merges;
- semantic plan and index transitions;
- resource deltas;
- finding introductions and resolutions;
- relative policy rules.

### API and CLI

Added plan import, optional live collection, plan retrieval, comparison creation/listing/retrieval, `planguard plan-import`, and `planguard compare`.

### UI

Added Plan Explorer, Comparison Workbench, Comparison Detail, Run Explorer plan links, and navigation. The UI renders canonical artifacts rather than recomputing plan or comparison semantics.

## Seeded demonstration

The seed runs the same relation-fan-out template and binding under one deterministic seed using naïve and optimized variants. It imports analyzed-format sequential-scan and index-scan fixtures without executing SQL and persists a collection receipt for each import. The resulting comparison is `valid_with_controlled_changes`, records the semantic scan/index transition, and passes a relative policy requiring query-count reduction.

## Validation results

- 36 tests passed;
- 3 optional suites were skipped because Django and Hypothesis were unavailable in the offline construction environment;
- Python source compilation passed;
- generated JSON Schema and TypeScript contracts reproduced byte-for-byte;
- 953 of 953 committed artifacts verified against their content-addressed objects;
- the rebuildable SQLite projection indexed all 953 artifacts;
- CLI plan import and comparability-aware comparison passed;
- all 20 TypeScript/TSX files transpiled without diagnostics;
- a full Vite production build was not run because npm dependencies were unavailable offline;
- the delta overlays Milestone D without requiring path deletion.
