# ADR 0005 — Scoped capture and immutable observations

## Decision

Capture is active only inside an explicit `AnalysisSession`. Every database execution becomes an
immutable `query_execution` artifact before normalization or detection.

## Consequences

- later analyzers can be rerun without recapturing;
- detector changes cannot rewrite historical facts;
- capture overhead is bounded and attributable;
- always-on APM behavior is outside the core package;
- nested sessions are rejected until operation graphs define their semantics.
