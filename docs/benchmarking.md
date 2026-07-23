# Benchmark methodology

A benchmark protocol declares warm-ups, measured repetitions, cache state, ordering, outlier treatment, environment requirements, timeout, dimensions, concurrency, and metrics.

PlanGuard preserves every sample. Invalid or timed-out observations remain visible with exclusion reasons. Robust summaries include median, P95, standard deviation, median absolute deviation, and descriptive confidence intervals.

## Scaling

Scaling classifications are based on measured points only. Log-log slope and fit quality are retained as evidence. Threshold transitions are represented separately from smooth growth. Reports explicitly state that these classifications are not formal Big-O proofs.

## Comparability

Structural query and plan evidence may remain comparable when timing does not. Environment references, cache protocol, dataset identity, concurrency, and changed scenario dimensions should be captured before a performance claim is accepted.

## Concurrency

Concurrent operations start behind a common barrier. Errors, timeouts, throughput, and adapter-provided lock metrics are aggregated. Failed workers are never removed from the record merely to improve a reported percentile.
