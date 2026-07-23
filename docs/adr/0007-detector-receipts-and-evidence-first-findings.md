# ADR 0007 — Detector receipts and evidence-first findings

## Decision

Every detector emits a receipt, including zero-finding and failed executions. Findings reference
separate evidence artifacts and carry distinct severity, confidence, limitations, and remediation.

## Consequences

Users can distinguish “nothing was found” from “nothing was checked.” Claims remain auditable and
future detectors can reuse evidence without copying calculations.
