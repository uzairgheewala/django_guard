# Milestone B Implementation Record

## Scope

Milestone B implements Phases 2–5 of the phased plan and establishes the first complete developer
MVP. It is an additive layer over Milestone A's immutable artifact kernel.

## Phase 2 — Capture runtime

Delivered:

- `AnalysisSession` and `profile(...)` context manager;
- context-local active-session state;
- manual query recording;
- optional Django execution wrappers;
- multiple connection aliases and vendor identity;
- success/failure, duration, row count, transaction depth, and origin capture;
- SQL omit/redact/preserve policies;
- parameter none/shape/shape-and-HMAC/preserve policies;
- explicit capture limits and limit-reached capability state;
- environment, capture policy, query executions, analysis, and final manifest persistence;
- failed operations still finalize an inspectable run.

Milestone B rejects nested active sessions rather than allowing ambiguous double capture. Nested
operation segmentation is reserved for the workload-graph milestone.

## Phase 3 — Normalization and family schemes

The built-in normalizer is deliberately conservative. It removes comments, normalizes whitespace,
redacts literals and driver placeholders, extracts common structural features, and labels each
result with `partial`, `fallback`, or `failed` parse quality. It does not claim semantic SQL
equivalence.

Each execution can be projected under several explicit schemes. Families are therefore views over
immutable observations rather than intrinsic query labels.

## Phase 4 — Findings

The detector engine isolates each detector and always emits a receipt. Receipts distinguish a
successful zero-finding analysis from a failed or unavailable analysis.

Initial detectors cover:

- exact repeated execution;
- structural repetition from one application origin;
- likely parameter-varying N+1 behavior;
- concentration of captured database time in one structural family.

Findings separate severity from confidence and include evidence, limitations, remediation category,
and source family references.

## Phase 5 — Budgets and surfaces

The policy engine evaluates generic selectors and absolute rules over runs, families, findings, and
detector receipts. It supports failure, warning, and non-evaluated states.

Surfaces include:

- pytest marker and fixture;
- CLI inspect, analyze, report, and policy evaluation;
- terminal, JSON, and standalone HTML reports;
- workbench run APIs;
- Run Explorer and Policy Studio UI.

## Artifact additions

- `planguard.query-execution.v1`
- `planguard.query-template.v1`
- `planguard.family-scheme.v1`
- `planguard.observed-query-family.v1`
- `planguard.evidence.v1`
- `planguard.finding.v1`
- `planguard.detector-receipt.v1`
- `planguard.budget-policy.v1`
- `planguard.budget-evaluation.v1`
- `planguard.analysis-summary.v1`

All contracts are generated into JSON Schema and TypeScript from the Pydantic source models.

## Known capability boundaries

- SQL parsing is conservative and marked partial rather than AST-complete.
- The N+1 detector cannot yet prove a parent-result dependency; workload graphs add that evidence.
- Policies are absolute; baseline-relative policies arrive with semantic comparison.
- PostgreSQL plan analysis is not present.
- The workbench is Explorer-only and cannot execute arbitrary database operations.
