import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getBenchmarkProtocols, getBenchmarkSeries, listBenchmarkSeries, runBenchmark, type ArtifactDocumentLike, type IndexedArtifactSummary } from "../lib/api";

function payload<T = Record<string, unknown>>(artifact: ArtifactDocumentLike): T {
  return artifact.payload as T;
}

export function BenchmarkLabPage() {
  const [protocols, setProtocols] = useState<ArtifactDocumentLike[]>([]);
  const [seriesList, setSeriesList] = useState<IndexedArtifactSummary[]>([]);
  const [selectedProtocol, setSelectedProtocol] = useState("");
  const [metricModel, setMetricModel] = useState("linear");
  const [series, setSeries] = useState<ArtifactDocumentLike | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => Promise.all([getBenchmarkProtocols(), listBenchmarkSeries(30)])
    .then(([catalog, stored]) => {
      setProtocols(catalog.items);
      setSeriesList(stored.items);
      if (!selectedProtocol && catalog.items.length) setSelectedProtocol(catalog.items[0].artifact_id);
    });

  useEffect(() => { refresh().catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason))); }, []);

  const protocol = protocols.find((item) => item.artifact_id === selectedProtocol);
  const seriesPayload = series ? payload<any>(series) : null;
  const measuredSamples = useMemo(() => (seriesPayload?.samples ?? []).filter((item: any) => !item.warmup), [seriesPayload]);

  const execute = async () => {
    if (!selectedProtocol) return;
    setBusy(true); setError(null);
    try {
      const result = await runBenchmark(selectedProtocol, metricModel);
      setSeries(result);
      await refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  };

  return <section>
    <header className="page-header"><div><p className="eyebrow">Milestone G</p><h1>Benchmark and experiment laboratory</h1><p>Run repeated, receipt-bearing series; separate warm-ups from measurements; preserve failed samples; and classify only observed scaling over the measured range.</p></div></header>
    {error && <div className="error-banner" role="alert">{error}</div>}
    <div className="section-grid benchmark-grid">
      <article className="panel">
        <h2>Protocol</h2>
        <label>Benchmark protocol<select value={selectedProtocol} onChange={(event) => setSelectedProtocol(event.target.value)}>{protocols.map((item) => <option key={item.artifact_id} value={item.artifact_id}>{String(payload<any>(item).title)}</option>)}</select></label>
        <label>Demonstration metric model<select value={metricModel} onChange={(event) => setMetricModel(event.target.value)}><option value="constant">Constant</option><option value="linear">Linear</option><option value="superlinear">Superlinear</option><option value="threshold">Threshold transition</option></select></label>
        {protocol && <div className="definition-list"><span>Warm-ups<strong>{String(payload<any>(protocol).warmup_iterations)}</strong></span><span>Measured iterations<strong>{String(payload<any>(protocol).measured_iterations)}</strong></span><span>Cache protocol<strong>{String(payload<any>(protocol).cache_protocol)}</strong></span><span>Outliers<strong>{String(payload<any>(protocol).outlier_policy)}</strong></span></div>}
        <button className="primary-button" type="button" disabled={busy || !selectedProtocol} onClick={execute}>{busy ? "Running…" : "Run controlled series"}</button>
      </article>
      <article className="panel">
        <h2>Stored series</h2>
        <div className="compact-list">{seriesList.map((item) => <button className="plain-row" type="button" key={item.artifact_id} onClick={() => getBenchmarkSeries(item.artifact_id).then(setSeries)}><span><strong>{item.title ?? item.artifact_id}</strong><code>{item.artifact_id}</code></span><span>{item.status ?? "series"}</span></button>)}{!seriesList.length && <p className="muted">No persisted series yet.</p>}</div>
      </article>
    </div>
    {series && <>
      <div className="metric-grid four-up">
        <article className="metric-card"><span>Status</span><strong>{String(seriesPayload.status)}</strong><small>Failed samples remain visible</small></article>
        <article className="metric-card"><span>Samples</span><strong>{String(seriesPayload.samples?.length ?? 0)}</strong><small>{measuredSamples.length} measured</small></article>
        <article className="metric-card"><span>Metrics</span><strong>{String(seriesPayload.distributions?.length ?? 0)}</strong><small>Robust summaries</small></article>
        <article className="metric-card"><span>Scaling</span><strong>{String(seriesPayload.scaling_assessments?.length ?? 0)}</strong><small>Descriptive classifications</small></article>
      </div>
      <article className="panel">
        <div className="section-heading"><div><h2>Metric distributions</h2><p>Intervals are descriptive and retain exclusion counts.</p></div><Link to={`/artifacts/${series.artifact_id}`}>Open artifact</Link></div>
        <div className="table-wrap"><table><thead><tr><th>Metric</th><th>n</th><th>Excluded</th><th>Median</th><th>P95</th><th>Confidence interval</th></tr></thead><tbody>{(seriesPayload.distributions ?? []).map((item: any) => <tr key={item.metric_key}><td>{item.metric_key}</td><td>{item.sample_count}</td><td>{item.excluded_count}</td><td>{item.median?.toFixed?.(2) ?? "—"}</td><td>{item.p95?.toFixed?.(2) ?? "—"}</td><td>{item.confidence_low?.toFixed?.(2) ?? "—"} – {item.confidence_high?.toFixed?.(2) ?? "—"}</td></tr>)}</tbody></table></div>
      </article>
      <article className="panel"><h2>Observed scaling</h2><div className="compact-list">{(seriesPayload.scaling_assessments ?? []).map((item: any) => <div className="plain-row static" key={item.metric_key}><span><strong>{item.metric_key}</strong><small>{item.independent_dimension} · slope {item.slope?.toFixed?.(3) ?? "—"}</small></span><span className="status-pill">{item.classification}</span></div>)}</div></article>
    </>}
  </section>;
}
