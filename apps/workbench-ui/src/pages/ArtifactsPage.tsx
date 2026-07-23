import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { importArtifact, listArtifacts, rebuildRegistry, type IndexedArtifactSummary } from "../lib/api";

export function ArtifactsPage() {
  const [items, setItems] = useState<IndexedArtifactSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [importing, setImporting] = useState(false);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("");

  const refresh = () => listArtifacts({ q: query, kind, limit: 100 })
    .then((response) => { setItems(response.items); setTotal(response.total); })
    .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)));

  useEffect(() => { const handle = window.setTimeout(refresh, 150); return () => window.clearTimeout(handle); }, [query, kind]);

  const handleImport = async () => {
    setImporting(true); setError(null);
    try { await importArtifact(draft); setDraft(""); refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setImporting(false); }
  };

  return <section>
    <header className="page-header"><div><p className="eyebrow">Registry</p><h1>Artifacts</h1><p>Search the disposable metadata index while preserving canonical JSON as the only authority.</p></div><button type="button" className="secondary-button" onClick={() => rebuildRegistry().then(refresh).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)))}>Rebuild index</button></header>
    {error && <div className="error-banner" role="alert">{error}</div>}
    <div className="filter-bar"><label>Search<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="ID, schema, title, mechanism…" /></label><label>Kind<select value={kind} onChange={(event) => setKind(event.target.value)}><option value="">All kinds</option><option value="run_manifest">Run manifests</option><option value="workload_graph">Workload graphs</option><option value="workload_episode">Episodes</option><option value="finding">Findings</option><option value="observed_query_family">Query families</option><option value="query_execution">Query executions</option></select></label><span className="filter-count">{items.length} of {total}</span></div>
    <div className="table-wrap"><table><thead><tr><th>Artifact</th><th>Kind</th><th>Context</th><th>Created</th><th>Integrity hash</th></tr></thead><tbody>{items.map((item) => <tr key={item.artifact_id}><td><Link to={`/artifacts/${item.artifact_id}`}>{item.artifact_id}</Link></td><td><span className="badge">{item.artifact_kind}</span></td><td>{item.title ?? item.mechanism_key ?? item.motif_key ?? item.run_id ?? "—"}</td><td>{new Date(item.created_at).toLocaleString()}</td><td><code>{item.content_hash?.slice(0, 22)}…</code></td></tr>)}</tbody></table>{items.length === 0 && <p className="empty-state">No valid artifacts match the active filters.</p>}</div>
    <article className="panel import-panel"><h2>Import one sealed artifact</h2><p>Validation, integrity verification, immutable persistence, and index projection run before the artifact becomes navigable.</p><textarea value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="{ &quot;schema_version&quot;: &quot;...&quot;, ... }" rows={8} /><button type="button" className="primary-button" onClick={handleImport} disabled={!draft || importing}>{importing ? "Importing…" : "Validate and import"}</button></article>
  </section>;
}
