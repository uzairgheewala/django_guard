# PlanGuard Workbench UI

Milestone F adds two artifact-backed surfaces:

```text
/universes
/detectors
```

The Universe Explorer exposes axes, constraints, representative-set generation, coverage status, interaction coverage, and cell provenance. The Detector Laboratory evaluates behavioral novelty, captures labeled counterexamples, minimizes them while preserving an explicit predicate, and promotes reviewed cases into the corpus.

All edits and actions serialize to canonical PlanGuard artifacts. Coverage state, novelty classification, and minimization results are not inferred only in browser state.

```bash
npm install
npm run dev
```

Set `VITE_PLANGUARD_API_BASE` when the API is not at `http://127.0.0.1:8000`.
