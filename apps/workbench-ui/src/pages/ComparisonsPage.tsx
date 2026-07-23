import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { createComparison, listComparisons, listRuns, type IndexedArtifactSummary, type RunListItem } from "../lib/api";

export function ComparisonsPage() {
  const [items, setItems] = useState<IndexedArtifactSummary[]>([]);
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [baseline, setBaseline] = useState("");
  const [candidate, setCandidate] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const reload = () => listComparisons().then((value) => setItems(value.items));
  useEffect(() => { reload(); listRuns({ limit: 100 }).then((value) => { setRuns(value.items); if (value.items[1]) setBaseline(value.items[1].artifact_id); if (value.items[0]) setCandidate(value.items[0].artifact_id); }); }, []);
  async function compare() {
    setMessage("Comparing…");
    try { const report = await createComparison(baseline, candidate); setMessage(`Created ${report.artifact_id}`); await reload(); }
    catch (reason) { setMessage(reason instanceof Error ? reason.message : String(reason)); }
  }
  return <section>
    <header className="page-header"><div><p className="eyebrow">Comparability before causality</p><h1>Comparison Workbench</h1><p>Compare workload structure, plans, findings, and resources without presenting uncontrolled timing differences as causal improvements.</p></div></header>
    <article className="panel comparison-builder">
      <label>Baseline<select value={baseline} onChange={(event) => setBaseline(event.target.value)}>{runs.map((run) => <option key={run.artifact_id} value={run.artifact_id}>{run.name} · {run.artifact_id.slice(0, 16)}</option>)}</select></label>
      <span aria-hidden="true">→</span>
      <label>Candidate<select value={candidate} onChange={(event) => setCandidate(event.target.value)}>{runs.map((run) => <option key={run.artifact_id} value={run.artifact_id}>{run.name} · {run.artifact_id.slice(0, 16)}</option>)}</select></label>
      <button type="button" onClick={compare} disabled={!baseline || !candidate || baseline === candidate}>Create comparison</button>
      {message && <p aria-live="polite">{message}</p>}
    </article>
    <div className="comparison-list">{items.map((item) => <Link className="panel comparison-row" to={`/comparisons/${item.artifact_id}`} key={item.artifact_id}><span><strong>{item.title ?? item.artifact_id}</strong><small>{item.artifact_id}</small></span><span className={`badge comparison-${item.status}`}>{item.status ?? "unknown"}</span></Link>)}</div>
  </section>;
}
