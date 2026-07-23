import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { buildRelease, getDemonstrations, getReleases, type ArtifactDocumentLike } from "../lib/api";

export function ReleasePage() {
  const [cases, setCases] = useState<Array<{ artifact: ArtifactDocumentLike; valid: boolean; missing: string[] }>>([]);
  const [releases, setReleases] = useState<ArtifactDocumentLike[]>([]);
  const [releaseKey, setReleaseKey] = useState("planguard-0.7.0");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const refresh = () => Promise.all([getDemonstrations(), getReleases()]).then(([demo, rel]) => { setCases(demo.items); setReleases(rel.items); });
  useEffect(() => { refresh().catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason))); }, []);
  const create = async () => { setBusy(true); try { await buildRelease({ release_key: releaseKey, status: "candidate" }); await refresh(); } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); } finally { setBusy(false); } };
  return <section><header className="page-header"><div><p className="eyebrow">OSS maturity</p><h1>Demonstration corpus and release manifest</h1><p>Verify that each documented case retains all canonical inputs, then bind schemas, plugins, security evidence, compatibility, checksums, and validation results into one immutable release candidate.</p></div></header>{error && <div className="error-banner" role="alert">{error}</div>}
    <article className="panel release-builder"><label>Release key<input value={releaseKey} onChange={(event) => setReleaseKey(event.target.value)} /></label><button className="primary-button" type="button" disabled={busy} onClick={create}>{busy ? "Building…" : "Build release candidate"}</button></article>
    <article className="panel"><h2>Demonstration cases</h2><div className="compact-list">{cases.map((item) => { const data: any = item.artifact.payload; return <div className="plain-row static" key={item.artifact.artifact_id}><span><strong>{data.title}</strong><small>{data.case_key} · {data.documentation_path}</small></span><span><span className={`status-pill ${item.valid ? "supported" : "failed"}`}>{item.valid ? "verified" : "incomplete"}</span> <Link to={`/artifacts/${item.artifact.artifact_id}`}>Artifact</Link></span></div>; })}{!cases.length && <p className="muted">No demonstration cases have been seeded.</p>}</div></article>
    <article className="panel"><h2>Release manifests</h2><div className="compact-list">{releases.map((item) => { const data: any = item.payload; return <div className="plain-row static" key={item.artifact_id}><span><strong>{data.release_key}</strong><small>{data.artifact_schema_versions?.length ?? 0} schemas · {data.plugin_manifest_refs?.length ?? 0} plugins · {data.demonstration_case_refs?.length ?? 0} cases</small></span><span><span className="status-pill">{data.status}</span> <Link to={`/artifacts/${item.artifact_id}`}>Inspect</Link></span></div>; })}</div></article>
  </section>;
}
