# PlanGuard Workbench UI

Milestone G completes the local artifact workbench with four mature-operations surfaces:

```text
/benchmarks
/security
/plugins
/releases
```

The Benchmark Laboratory configures repeatable protocols, executes ordered scenario series, and distinguishes structural evidence from noisy timing observations. The Security Center audits stored artifacts, previews schema-preserving sanitization, verifies content and provenance trust, and exposes quarantine outcomes. The Plugin Registry displays contract, capability, determinism, and safety declarations. The Release Center verifies demonstration cases and assembles canonical release manifests.

All meaningful state is persisted through versioned PlanGuard artifacts. The browser does not invent benchmark conclusions, trust decisions, plugin contracts, or release status.

```bash
npm install
npm run dev
```

Set `VITE_PLANGUARD_API_BASE` when the API is not at `http://127.0.0.1:8000`.
