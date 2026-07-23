# Artifact schema policy

Pydantic models are the canonical contract source. JSON Schema and TypeScript definitions are generated from the same union.

Persisted documents include explicit defaults and nulls, a qualified SHA-256 content hash, provenance, producer identity, and namespaced extensions. Unknown extensions round-trip. Existing v1 contracts are not reinterpreted when later artifact kinds are added.

Event artifacts use unique identifiers and real timestamps. Reusable semantic definitions may use content-derived identifiers and a stable semantic timestamp. Schema versions and package versions remain independent.
