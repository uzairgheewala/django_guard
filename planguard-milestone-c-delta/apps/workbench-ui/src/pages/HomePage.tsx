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
          <p className="eyebrow">Milestone C</p>
          <h1>Visual workload analysis product</h1>
          <p>Navigate immutable evidence through an indexed local workbench, switch explicit family lenses, and inspect workload topology, inferred causal edges, reusable motifs, and episode matches.</p>
        </div>
      </header>

      {error && <div className="error-banner" role="alert">{error}</div>}
      <div className="metric-grid four-up">
        <article className="metric-card"><span>Artifacts</span><strong>{stats?.total_artifacts ?? "—"}</strong><small>Canonical source documents</small></article>
        <article className="metric-card"><span>Runs</span><strong>{stats?.runs ?? "—"}</strong><small>Captured operations</small></article>
        <article className="metric-card"><span>Findings</span><strong>{stats?.findings ?? "—"}</strong><small>Evidence-backed interpretations</small></article>
        <article className="metric-card"><span>Episodes</span><strong>{stats?.episodes ?? "—"}</strong><small>Reusable motif occurrences</small></article>
      </div>

      <div className="callout">
        <div><h2>Explore the Milestone C workload</h2><p>The sample graph synchronizes operation, query execution, query family, transaction, episode, and finding projections while keeping inferred relationships visibly uncertain.</p></div>
        <Link className="primary-button" to="/runs/run_demo_c_001">Open sample run</Link>
      </div>

      <div className="section-grid">
        <article className="panel"><h2>Rebuildable registry</h2><p>SQLite accelerates search and provenance traversal, but every row can be reconstructed from immutable artifact bundles.</p></article>
        <article className="panel"><h2>Observed versus inferred</h2><p>Every edge declares whether it was directly observed, deterministically derived, or causally inferred with confidence and evidence.</p></article>
        <article className="panel"><h2>Motifs are not findings</h2><p>A workload episode describes a matched structural pattern. Detector and policy layers decide whether that pattern is harmful in context.</p></article>
        <article className="panel"><h2>Lens synchronization</h2><p>Timeline, families, graph, and episodes remain projections of the same execution evidence rather than separate dashboard calculations.</p></article>
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
