import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getPlugins, type ArtifactDocumentLike } from "../lib/api";

export function PluginsPage() {
  const [items, setItems] = useState<ArtifactDocumentLike[]>([]);
  const [discoveries, setDiscoveries] = useState<Array<{ manifest: ArtifactDocumentLike; loaded: boolean; error?: string | null }>>([]);
  const [error, setError] = useState<string | null>(null);
  const load = (discover = false) => getPlugins(discover).then((result) => { setItems(result.items); setDiscoveries(result.discovery); }).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)));
  useEffect(() => { load(); }, []);
  return <section><header className="page-header"><div><p className="eyebrow">Extension boundary</p><h1>Plugin contracts</h1><p>Inspect component type, accepted and emitted schemas, capability requirements, determinism, configuration contracts, and safety profiles before enabling an extension.</p></div><button type="button" onClick={() => load(true)}>Discover entry points</button></header>{error && <div className="error-banner" role="alert">{error}</div>}
    <div className="plugin-grid">{items.map((item) => { const data: any = item.payload; return <article className="panel" key={item.artifact_id}><div className="section-heading"><div><h2>{data.plugin_key}</h2><p>{data.description}</p></div><span className="status-pill">{data.component_type}</span></div><div className="definition-list"><span>Version<strong>{data.plugin_version}</strong></span><span>Determinism<strong>{data.determinism}</strong></span><span>Entry point<strong>{data.entry_point_name}</strong></span><span>Default<strong>{data.enabled_by_default ? "enabled" : "disabled"}</strong></span></div><p className="muted">Requires: {(data.required_capabilities ?? []).join(", ") || "none"}</p><Link to={`/artifacts/${item.artifact_id}`}>Inspect manifest</Link></article>; })}</div>
    {discoveries.length > 0 && <article className="panel"><h2>Discovery receipts</h2>{discoveries.map((item) => <div className="plain-row static" key={item.manifest.artifact_id}><span><strong>{String((item.manifest.payload as any).entry_point_name)}</strong><small>{item.error ?? "Loaded successfully"}</small></span><span className={`status-pill ${item.loaded ? "supported" : "failed"}`}>{item.loaded ? "loaded" : "failed"}</span></div>)}</article>}
  </section>;
}
