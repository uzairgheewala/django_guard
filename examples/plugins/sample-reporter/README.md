# Sample reporter plugin

This package demonstrates the public `planguard.plugins` entry-point contract. It declares a canonical `PluginManifestArtifact` alongside a deterministic reporter callable. Install PlanGuard first, then install this directory in editable mode and run:

```bash
planguard plugin-list --discover
```

The example deliberately performs no network access and no filesystem writes.
