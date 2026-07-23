# PlanGuard — Milestone F

Milestone F turns PlanGuard's generic scenario philosophy into an explicit, machine-verifiable coverage system and a self-improving counterexample corpus.

```text
declared universe profile
  → typed axes and constrained domains
  → coverage obligations
  → risk-weighted representative scenarios
  → scenario execution and evidence
  → coverage ledger
  → behavioral novelty
  → labeled counterexample
  → predicate-preserving minimization
  → reviewed corpus promotion
```

The source of truth remains immutable, versioned JSON artifacts. Coverage is always relative to a declared universe profile; PlanGuard never equates a finite seed corpus with theoretical completeness.

## Milestone F capabilities

### Declared universe profiles

A `UniverseProfileArtifact` declares:

- the target application/database capability profile;
- typed axes and representative partitions;
- applicability, exclusion, implication, and dependency constraints;
- coverage strategies and risk weights;
- explicit unknown and unsupported handling.

The built-in `django-postgres-core.v1` profile covers generic workload topology, application binding, implementation variant, data scale, tenant skew, parent cardinality, relation fan-out, transaction scope, and mutation class. Applications can register additional axes without changing the core artifact model.

### Constrained coverage obligations

PlanGuard does not build a naïve Cartesian product. It constructs auditable obligation cells for:

- single-axis partitions;
- boundary values;
- selected high-risk pairwise interactions;
- motif coverage;
- mutation coverage;
- metamorphic scale relations.

Every cell is classified as:

```text
covered
uncovered
inapplicable
unsupported
unknown
```

A `CoverageReportArtifact` links each covered cell to the exact scenario instances and runs that satisfy it.

### Representative-set generation

The deterministic generator:

1. binds generic scenario templates to available application adapters;
2. creates valid candidate instances;
3. excludes incompatible mutations and constrained combinations;
4. greedily selects cases by risk-weighted marginal coverage;
5. records each case's exact marginal contribution;
6. reports remaining uncovered and unsupported obligations.

The result is a versioned `RepresentativeSetArtifact`, not a hidden test-runner decision.

### Behavioral novelty

A `NoveltySignatureArtifact` compares a run's behavior with a reference corpus using a stable feature vector containing:

- query shapes and statement kinds;
- family execution regimes;
- workload motifs;
- finding mechanisms;
- plan node types and plan-shape fingerprints.

Classification is explicit: `known`, `partial`, or `novel`. Novelty means “not represented by the selected corpus,” not “incorrect.”

### Counterexample lifecycle

Unexpected behavior can be captured as a labeled `CounterexampleCandidateArtifact`:

```text
false_positive
false_negative
unexpected_regression
unexpected_non_regression
unclassified_behavior
```

Every candidate includes an explicit preserved predicate. The minimizer records each attempted shrink and keeps only transformations that preserve that predicate. Reviewed minimized cases can be promoted through a separate `CorpusPromotionArtifact` into detector fixtures, scenario instances, universe extensions, mutations, or golden-plan corpora.

### Workbench UI

New surfaces:

- `/universes` — axis browser, constraints, representative-set builder, coverage ledger, interaction coverage, and provenance;
- `/detectors` — novelty evaluation, counterexample labeling, minimization, and corpus promotion.

All previous Run, Family, Workload Graph, Scenario, Plan, Comparison, Policy, Artifact, and Capability views remain available.

## Install

```bash
python -m pip install -e .
python -m pip install -e '.[api]'
python -m pip install -e '.[dev]'
```

## CLI

```bash
planguard universe-catalog --store examples/store

planguard universe-generate \
  --store examples/store \
  --maximum-cases 16 \
  --seed 23

planguard universe-evaluate \
  --store examples/store

planguard novelty-evaluate RUN_ID \
  --store examples/store

planguard counterexample-create RUN_ID false_positive \
  --scenario-instance-id SCENARIO_INSTANCE_ID \
  --predicate-kind finding_present \
  --predicate-key likely_n_plus_one \
  --store examples/store

planguard counterexample-minimize COUNTEREXAMPLE_ID \
  --store examples/store

planguard counterexample-promote COUNTEREXAMPLE_ID \
  --minimization-id MINIMIZATION_ID \
  --store examples/store
```

All earlier capture, policy, search, scenario, plan, and comparison commands remain available.

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

## New contracts

```text
planguard.universe-profile.v1
planguard.representative-set.v1
planguard.coverage-report.v1
planguard.novelty-signature.v1
planguard.counterexample-candidate.v1
planguard.minimization-run.v1
planguard.corpus-promotion.v1
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

The Milestone F seed persists the built-in universe, a deterministic 16-case representative basis, four executed representative scenarios, novelty signatures, a complete coverage ledger, and a predicate-preserving counterexample/minimization/promotion chain.

## Scope and honesty

- coverage is relative to a named, versioned universe profile;
- partial coordinates are coverage obligations, not complete scenario claims;
- unsupported, inapplicable, unknown, and uncovered remain distinct;
- novelty is descriptive, not automatically pathological;
- minimization never mutates the original scenario or run;
- corpus promotion is explicit and reviewable;
- no ORM/SQL rewriting or automatic index creation is introduced.
