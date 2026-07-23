# Milestone F implementation record

Milestone F implements Phases 12 and 13: declared universe coverage, representative generation, behavioral novelty, counterexample minimization, and corpus evolution.

## 1. Semantic additions

Seven canonical artifact contracts were added:

```text
planguard.universe-profile.v1
planguard.representative-set.v1
planguard.coverage-report.v1
planguard.novelty-signature.v1
planguard.counterexample-candidate.v1
planguard.minimization-run.v1
planguard.corpus-promotion.v1
```

The contracts preserve the existing artifact envelope, immutable identity, provenance, extension, and content-hash rules.

## 2. Universe model

A universe profile contains typed axes, parameter domains, constraints, target capabilities, coverage strategies, and extension points. The built-in Django/PostgreSQL profile is intentionally application-neutral and is realized through the existing generic scenario templates and academic bindings.

Coverage cells are obligation coordinates rather than full Cartesian-product scenarios. This permits exact statements such as “the `large` parent-count partition is covered” or “the `dominant tenant × missing composite index` interaction is uncovered” while keeping impossible combinations explicitly inapplicable.

## 3. Representative generation

The generator constructs candidate instances from valid template/binding pairs, variants, representative axis values, and compatible mutations. It then performs deterministic risk-weighted greedy selection. Each selection records only the obligations added at that selection step—its true marginal coverage contribution.

## 4. Coverage evaluation

Coverage evaluation maps persisted scenario instances and runs back into universe coordinates. Reports include:

- per-cell status and provenance;
- per-axis covered, uncovered, unsupported, and inapplicable partitions;
- pairwise and metamorphic interaction ratios;
- capability gaps;
- linked novelty artifacts;
- explicit limitations.

The seeded profile currently declares 357 obligations. The exact final seeded counts are recorded in the generated coverage artifact and release validation output rather than hardcoded into the engine.

## 5. Novelty and corpus evolution

Runs receive stable behavioral signatures composed from query, family, motif, finding, and plan features. A candidate can then be labeled, tied to an explicit preserved predicate, minimized through deterministic shrink steps, and promoted into one or more corpus targets.

The current minimizer provides generic structural reductions over scenario parameters and ordered mutations. Its predicate interface is intentionally open so later detector-, policy-, plan-, and result-equivalence evaluators can be registered without changing candidate artifacts.

## 6. API, CLI, and UI

The Workbench API exposes universe catalog, representative generation, coverage evaluation, novelty evaluation, counterexample creation, minimization, and promotion.

The CLI exposes equivalent operations. The Universe Explorer and Detector Laboratory use the same canonical documents and do not maintain independent frontend semantics.

## 7. Validation approach

Milestone F validation covers:

- deterministic cell enumeration;
- constraint status separation;
- representative-set determinism and marginal coverage;
- direct axis and interaction coverage;
- novelty classification;
- preserved-predicate minimization;
- corpus promotion;
- contract regeneration;
- artifact-store integrity;
- CLI workflows;
- UI syntax transpilation;
- delta-overlay reconstruction.

Optional Django and Hypothesis suites remain conditional on those dependencies being installed.
