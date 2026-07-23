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
          <p className="eyebrow">Milestone F</p>
          <h1>Universe coverage and corpus evolution</h1>
          <p>Declare the workload-behavior space, generate a compact representative scenario basis, measure exact coverage, and turn novel or misclassified behavior into minimized reusable counterexamples.</p>
        </div>
      </header>

      {error && <div className="error-banner" role="alert">{error}</div>}
      <div className="metric-grid four-up">
        <article className="metric-card"><span>Artifacts</span><strong>{stats?.total_artifacts ?? "—"}</strong><small>Canonical source documents</small></article>
        <article className="metric-card"><span>Runs</span><strong>{stats?.runs ?? "—"}</strong><small>Captured operations</small></article>
        <article className="metric-card"><span>Findings</span><strong>{stats?.findings ?? "—"}</strong><small>Evidence-backed interpretations</small></article>
        <article className="metric-card"><span>Coverage reports</span><strong>{stats?.coverage_reports ?? "—"}</strong><small>Declared-universe ledgers</small></article>
      </div>

      <div className="callout">
        <div><h2>Build the representative basis</h2><p>Select coverage strategies, generate deterministic scenario instances, and inspect every covered, uncovered, unsupported, and inapplicable obligation.</p></div>
        <Link className="primary-button" to="/universes">Open Universe Explorer</Link>
      </div>

      <div className="section-grid">
        <article className="panel"><h2>Constrained universes</h2><p>Axes, partitions, applicability rules, capabilities, and interactions are explicit rather than hidden in hand-written examples.</p></article>
        <article className="panel"><h2>Representative sets</h2><p>A deterministic greedy selector maximizes risk-weighted marginal coverage within a bounded case budget.</p></article>
        <article className="panel"><h2>Behavioral novelty</h2><p>Runs are summarized by query shapes, family regimes, motifs, findings, and plan structures, then compared against the corpus.</p></article>
        <article className="panel"><h2>Counterexample evolution</h2><p>Unexpected behavior can be labeled, shrunk under an explicit preserved predicate, reviewed, and promoted into reusable corpora.</p></article>
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
