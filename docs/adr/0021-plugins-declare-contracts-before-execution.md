# ADR 0021: Plugins declare contracts before execution

## Status

Accepted for Milestone G.

## Decision

Every plugin exposes a versioned `PluginManifestArtifact` before its component is invoked. The manifest declares component type, accepted and emitted artifact schemas, capability requirements, determinism, configuration schema, safety profile, and default enablement.

Discovery uses the `planguard.plugins` entry-point group. Duplicate keys fail closed. Missing capabilities prevent default-enabled plugins from loading. Execution is isolated behind explicit timeout handling, but in-process timeouts are not represented as a security sandbox.

## Consequences

The workbench can explain what a plugin claims to consume, produce, and require without executing it. Future process-isolated plugin runners can reuse the same manifest contract.
