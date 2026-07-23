# ADR 0020: Security actions are schema-preserving artifacts

## Status

Accepted for Milestone G.

## Decision

Redaction and sanitization operate through typed, schema-aware paths rather than blind text replacement over canonical JSON. The sanitized derivative and its receipt are immutable artifacts with provenance back to the source.

Invalid or oversized imports are quarantined outside the canonical store. Trust verification checks content hashes and available provenance references but does not equate local integrity with cryptographic authorship.

## Consequences

A security action can be inspected, repeated, and audited. Unsupported redaction targets fail explicitly instead of creating malformed artifacts. Signature verification can later extend the trust model without changing current integrity semantics.
