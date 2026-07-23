# ADR 0015: PostgreSQL plans are contextual evidence

Status: Accepted for Milestone E.

## Decision

Persist normalized PostgreSQL plans as immutable `plan_observation` artifacts associated with an explicit query family, representative execution or parameter regime, collection policy, database settings, and safety context.

Plan operators are not globally classified as good or bad. Detectors may make contextual claims only when their evidence requirements are satisfied, such as a sequential scan over a relation explicitly configured as high-volume.

Unknown PostgreSQL node attributes are retained under `unknown_attributes`, while common semantic fields are normalized for cross-run comparison.

## Consequences

- estimated and actual plans remain distinguishable;
- parameter-sensitive plans may coexist for one query shape;
- imported plans can be analyzed without executing SQL;
- live `EXPLAIN ANALYZE` is capability-gated and safety checked;
- raw JSON diffs are not used as regression policy inputs.
