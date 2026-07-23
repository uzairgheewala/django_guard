# ADR 0012: Separate scenario templates, bindings, instances, and runs

## Status
Accepted for Milestone D.

## Decision
A scenario is represented by four different artifact layers. Templates define domain-neutral roles,
parameters, variants, oracles, and operation topology. Bindings map roles to one application.
Instances bind parameters, mutations, variant, and seed. Runs record actual execution and receipts.

## Consequences
The same template may be rebound without copying semantics; generated instances are reproducible;
and execution evidence never mutates the scenario definition that produced it.
