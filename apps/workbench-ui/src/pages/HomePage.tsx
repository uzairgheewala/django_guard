import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getRegistryStats, listRuns, type RegistryStats, type RunListItem } from "../lib/api";

export function HomePage() {
  const [stats, setStats] = useState<RegistryStats | null>(null);
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getRegistryStats(), listRuns({ limit: 4 })])
      .then(([registry, recent]) => { setStats(registry); setRuns(recent.items); })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, []);

  return (
    <section>
      <header className="page-header">
        <div>
          <p className="eyebrow">Milestone G</p>
          <h1>Reliable experiments, safe artifacts, and OSS maturity</h1>
          <p>Run repeatable experiment series, protect sensitive evidence, verify artifact trust, inspect plugin contracts, and publish reproducible demonstration cases through immutable release manifests.</p>
        </div>
      </header>

      {error && <div className="error-banner" role="alert">{error}</div>}
      <div className="metric-grid four-up">
        <article className="metric-card"><span>Artifacts</span><strong>{stats?.total_artifacts ?? "—"}</strong><small>Canonical source documents</small></article>
        <article className="metric-card"><span>Runs</span><strong>{stats?.runs ?? "—"}</strong><small>Captured operations</small></article>
        <article className="metric-card"><span>Findings</span><strong>{stats?.findings ?? "—"}</strong><small>Evidence-backed interpretations</small></article>
        <article className="metric-card"><span>Benchmarks</span><strong>{stats?.benchmark_series ?? "—"}</strong><small>Repeated experiment series</small></article>
      </div>

      <div className="callout">
        <div><h2>Run a controlled experiment series</h2><p>Separate warm-ups, retain failures and exclusions, inspect robust summaries, and avoid mistaking one noisy timing for a causal optimization.</p></div>
        <Link className="primary-button" to="/benchmarks">Open Benchmark Lab</Link>
      </div>

      <div className="section-grid">
        <article className="panel"><h2>Reliable experiment series</h2><p>Protocols capture warm-ups, repetitions, cache conditions, exclusions, distributions, and observed scaling over declared dimensions.</p></article>
        <article className="panel"><h2>Artifact security</h2><p>Pattern-backed audits, schema-preserving sanitization, integrity verification, quotas, and quarantine keep evidence sharing explicit.</p></article>
        <article className="panel"><h2>Versioned plugins</h2><p>Every extension declares its component type, schemas, capabilities, determinism, configuration, and safety profile.</p></article>
        <article className="panel"><h2>Reproducible OSS cases</h2><p>Demonstration cases and release manifests bind canonical inputs, documentation, checksums, security evidence, and validation results.</p></article>
      </div>

      <article className="panel recent-runs-panel">
        <div className="section-heading"><div><h2>Recent runs</h2><p>Open any indexed operation.</p></div><Link to="/runs">View all</Link></div>
        <div className="recent-run-list">
          {runs.map((run) => <Link key={run.artifact_id} className="recent-run-row" to={`/runs/${run.artifact_id}`}><span><strong>{run.name}</strong><code>{run.artifact_id}</code></span><span>{run.inventory.by_kind.query_execution ?? 0} queries</span><span>{run.inventory.by_kind.workload_episode ?? 0} episodes</span></Link>)}
          {runs.length === 0 && <p className="muted">No indexed runs yet.</p>}
        </div>
      </article>
    </section>
  );
}
