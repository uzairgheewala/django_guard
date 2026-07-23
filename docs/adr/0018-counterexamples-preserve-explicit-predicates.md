# ADR 0018: Counterexamples preserve explicit predicates

Status: Accepted for Milestone F.

## Context

A surprising run is not enough to define a reproducible counterexample. Minimization can accidentally remove the behavior that made the case useful, and labels such as “false positive” or “unexpected regression” do not specify what must remain true.

## Decision

Every `CounterexampleCandidateArtifact` carries an explicit `PreservedPredicate`. The predicate identifies the subject and a structural condition that must survive minimization, such as:

- a detector finding remains present;
- a detector finding remains absent;
- a policy still fails;
- a plan transition remains;
- a workload motif remains;
- application results still diverge.

Minimization is a receipt-bearing sequence of deterministic shrink attempts. Each step records the attempted transformation, whether the preserved predicate survived, and the resulting complexity score. The original scenario and run artifacts are immutable. Promotion into the regression corpus is a separate, reviewable `CorpusPromotionArtifact`.

## Consequences

- A minimized case remains tied to the behavior it is intended to reproduce.
- False-positive, false-negative, regression, and novelty workflows share one model.
- Shrinkers can evolve independently while preserving auditable step histories.
- Procedural predicates can be added later without changing candidate identity semantics.
