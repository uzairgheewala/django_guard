# Milestone D implementation record

Milestone D implements Phases 8 and 9 of the PlanGuard program: the generic scenario kernel and the
deterministic academic performance laboratory.

## Core additions

- eight new persisted artifact contracts;
- typed roles, parameter domains, variants, operation graphs, oracles, and coverage obligations;
- scenario catalog registries and adapter protocol;
- deterministic instance identity and stable timestamps for semantic artifacts;
- binding validation, scaling, contrast, and greedy pairwise generation;
- receipt-bearing execution with failure-safe cleanup;
- scenario-to-analysis-run linkage in run manifests;
- dataset manifests with logical and materialized counts, distributions, constraints, and hashes.

## Academic laboratory

The catalog contains ten generic templates, ten bindings, and eight mutations. The in-memory adapter
materializes bounded representative data while retaining logical scale counts up to the large
profile. Every generated row remains institution-scoped. Both naïve and optimized variants are
exercised by automated tests for every binding.

An optional Django app supplies equivalent shared-schema model shapes and tenant-aware indexes for a
future real PostgreSQL adapter without introducing a Django dependency into `planguard-core`.

## Workbench integration

The API exposes catalog, instantiation, execution, scenario-run listing, and scenario-run detail
resources. `/scenarios` serializes controls into canonical instance documents, shows phase receipts
and oracle evaluations, and links to the existing workload analysis screens.

## Validation

The release candidate passed the following validation:

- 31 tests passed;
- 3 optional suites were skipped because Django and Hypothesis were unavailable in the offline construction environment;
- all 825 committed sample artifacts passed pointer and content-hash verification;
- all 14 seeded scenario executions completed successfully;
- every generic academic binding was exercised in both naïve and optimized variants by the automated suite;
- generated JSON Schema and TypeScript contracts reproduced byte-for-byte;
- CLI catalog, instantiation, and execution workflows passed against an isolated artifact store;
- all 16 TypeScript/TSX source files passed syntax transpilation;
- the changed-files-only overlay reproduced the complete Milestone D canonical tree from Milestone C;
- the packaged ZIP passed archive-integrity testing.

A full Vite production build was not run because npm dependencies were unavailable in the offline
construction environment. The disposable SQLite registry projection is intentionally omitted from
the delta because it is rebuilt from canonical JSON artifacts.
