import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { JsonTree } from "../components/JsonTree";
import {
  executeScenario,
  getScenarioCatalog,
  listScenarioRuns,
  type ArtifactDocumentLike,
  type ScenarioCatalogResponse,
  type ScenarioExecutionResponse,
  type IndexedArtifactSummary,
} from "../lib/api";

function text(value: unknown, fallback = "unknown"): string {
  return typeof value === "string" ? value : fallback;
}

function number(value: unknown, fallback = 0): number {
  return typeof value === "number" ? value : fallback;
}

interface MutationSelection {
  mutation_key: string;
  parameters: Record<string, unknown>;
}

export function ScenarioStudioPage() {
  const [catalog, setCatalog] = useState<ScenarioCatalogResponse | null>(null);
  const [runs, setRuns] = useState<IndexedArtifactSummary[]>([]);
  const [templateKey, setTemplateKey] = useState("relation-access-fanout.v1");
  const [bindingKey, setBindingKey] = useState("academic.plan-item-course.v1");
  const [variant, setVariant] = useState("naive");
  const [scaleProfile, setScaleProfile] = useState("tiny");
  const [tenantSkew, setTenantSkew] = useState("uniform");
  const [parentCount, setParentCount] = useState(8);
  const [relationFanout, setRelationFanout] = useState(5);
  const [batchSize, setBatchSize] = useState(10);
  const [pageOffset, setPageOffset] = useState(0);
  const [transactionScope, setTransactionScope] = useState("autocommit");
  const [seed, setSeed] = useState(1);
  const [mutations, setMutations] = useState<MutationSelection[]>([]);
  const [result, setResult] = useState<ScenarioExecutionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const refreshRuns = () => listScenarioRuns({ limit: 12 }).then((response) => setRuns(response.items));

  useEffect(() => {
    getScenarioCatalog()
      .then((response) => {
        setCatalog(response);
        const first = response.templates[0];
        if (first) setTemplateKey(text(first.payload.template_key));
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)));
    refreshRuns().catch(() => undefined);
  }, []);

  const selectedTemplate = useMemo(
    () => catalog?.templates.find((item) => item.payload.template_key === templateKey) ?? null,
    [catalog, templateKey],
  );
  const compatibleBindings = useMemo(
    () => catalog?.bindings.filter((item) => {
      const ref = item.payload.template_ref as Record<string, unknown> | undefined;
      return ref?.artifact_id === selectedTemplate?.artifact_id;
    }) ?? [],
    [catalog, selectedTemplate],
  );

  useEffect(() => {
    if (compatibleBindings.length && !compatibleBindings.some((item) => item.payload.binding_key === bindingKey)) {
      setBindingKey(text(compatibleBindings[0].payload.binding_key));
    }
  }, [compatibleBindings, bindingKey]);

  const toggleMutation = (key: string) => {
    setMutations((current) => current.some((item) => item.mutation_key === key)
      ? current.filter((item) => item.mutation_key !== key)
      : [...current, { mutation_key: key, parameters: {} }]);
  };

  const runScenario = async () => {
    setRunning(true);
    setError(null);
    try {
      const response = await executeScenario({
        template_key: templateKey,
        binding_key: bindingKey,
        variant_key: variant,
        seed,
        parameters: {
          scale_profile: scaleProfile,
          tenant_skew: tenantSkew,
          parent_count: parentCount,
          relation_fanout: relationFanout,
          batch_size: batchSize,
          page_offset: pageOffset,
          transaction_scope: transactionScope,
        },
        mutations,
        tags: ["scenario-studio"],
      });
      setResult(response);
      await refreshRuns();
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setRunning(false);
    }
  };

  if (!catalog && !error) return <p className="empty-state">Loading scenario catalog…</p>;
  if (!catalog) return <div className="error-banner" role="alert">{error}</div>;

  const variants = (selectedTemplate?.payload.variants as Array<Record<string, unknown>> | undefined) ?? [];
  const oracleEvaluations = (result?.scenario_run.payload.oracle_evaluations as Array<Record<string, unknown>> | undefined) ?? [];

  return (
    <section>
      <header className="page-header">
        <div>
          <p className="eyebrow">Generic laboratory</p>
          <h1>Scenario Studio</h1>
          <p>Bind a domain-neutral workload template, choose a deterministic instance, stack ordered mutations, and inspect the resulting run artifacts.</p>
        </div>
        <span className={`badge ${catalog.execution_enabled ? "status-completed" : "status-failed"}`}>
          {catalog.execution_enabled ? "Laboratory enabled" : "Explorer only"}
        </span>
      </header>

      {error && <div className="error-banner" role="alert">{error}</div>}

      <div className="scenario-layout">
        <div className="scenario-controls">
          <article className="panel">
            <h2>1. Template and binding</h2>
            <label>Generic scenario template
              <select value={templateKey} onChange={(event) => setTemplateKey(event.target.value)}>
                {catalog.templates.map((item) => <option key={item.artifact_id} value={text(item.payload.template_key)}>{text(item.payload.title)}</option>)}
              </select>
            </label>
            <label>Academic binding
              <select value={bindingKey} onChange={(event) => setBindingKey(event.target.value)}>
                {compatibleBindings.map((item) => <option key={item.artifact_id} value={text(item.payload.binding_key)}>{text(item.payload.binding_key)}</option>)}
              </select>
            </label>
            {selectedTemplate && <div className="scenario-template-summary">
              <p>{text(selectedTemplate.payload.description)}</p>
              <div className="chip-row">{((selectedTemplate.payload.tags as string[]) ?? []).map((tag) => <span className="badge" key={tag}>{tag}</span>)}</div>
            </div>}
          </article>

          <article className="panel">
            <h2>2. Variant and dimensions</h2>
            <label>Implementation variant
              <select value={variant} onChange={(event) => setVariant(event.target.value)}>
                {variants.map((item) => <option key={text(item.variant_key)} value={text(item.variant_key)}>{text(item.title)}</option>)}
              </select>
            </label>
            <div className="scenario-form-grid">
              <label>Scale profile<select value={scaleProfile} onChange={(event) => setScaleProfile(event.target.value)}><option>tiny</option><option>small</option><option>medium</option><option>large</option></select></label>
              <label>Tenant skew<select value={tenantSkew} onChange={(event) => setTenantSkew(event.target.value)}><option>uniform</option><option>dominant</option><option>zipf</option></select></label>
              <label>Parent count<input type="number" min={0} max={1000} value={parentCount} onChange={(event) => setParentCount(Number(event.target.value))} /></label>
              <label>Relation fan-out<input type="number" min={0} max={100} value={relationFanout} onChange={(event) => setRelationFanout(Number(event.target.value))} /></label>
              <label>Batch size<input type="number" min={1} max={1000} value={batchSize} onChange={(event) => setBatchSize(Number(event.target.value))} /></label>
              <label>Page offset<input type="number" min={0} value={pageOffset} onChange={(event) => setPageOffset(Number(event.target.value))} /></label>
              <label>Transaction scope<select value={transactionScope} onChange={(event) => setTransactionScope(event.target.value)}><option>autocommit</option><option>short_atomic</option><option>long_atomic</option></select></label>
              <label>Seed<input type="number" value={seed} onChange={(event) => setSeed(Number(event.target.value))} /></label>
            </div>
          </article>

          <article className="panel">
            <h2>3. Ordered mutations</h2>
            <div className="mutation-list">
              {catalog.mutations.map((item) => {
                const key = text(item.payload.mutation_key);
                const checked = mutations.some((mutation) => mutation.mutation_key === key);
                return <label className={`mutation-row ${checked ? "selected" : ""}`} key={item.artifact_id}>
                  <input type="checkbox" checked={checked} onChange={() => toggleMutation(key)} />
                  <span><strong>{text(item.payload.title)}</strong><small>{text(item.payload.description)}</small></span>
                </label>;
              })}
            </div>
            <button className="primary-button" type="button" disabled={running || !catalog.execution_enabled} onClick={runScenario}>
              {running ? "Running scenario…" : "Instantiate and run"}
            </button>
          </article>
        </div>

        <div className="scenario-results">
          <article className="panel">
            <h2>Execution result</h2>
            {!result && <p className="empty-state">Run an instance to inspect its dataset, phase receipts, oracles, and linked workload analysis.</p>}
            {result && <>
              <div className="metric-grid four-up">
                <div className="metric-card"><span>Status</span><strong>{text(result.scenario_run.payload.status)}</strong></div>
                <div className="metric-card"><span>Phases</span><strong>{result.phase_receipts.length}</strong></div>
                <div className="metric-card"><span>Oracles</span><strong>{oracleEvaluations.length}</strong></div>
                <div className="metric-card"><span>Queries</span><strong>{number(result.phase_receipts.find((item) => item.payload.phase_key === "execute_operation")?.payload.statistics && (result.phase_receipts.find((item) => item.payload.phase_key === "execute_operation")?.payload.statistics as Record<string, unknown>).query_count)}</strong></div>
              </div>
              <div className="result-links">
                <Link to={`/artifacts/${result.scenario_run.artifact_id}`}>Scenario run artifact</Link>
                {result.analysis_run_id && <Link to={`/runs/${result.analysis_run_id}`}>Open workload analysis</Link>}
                {result.dataset_manifest && <Link to={`/artifacts/${result.dataset_manifest.artifact_id}`}>Dataset manifest</Link>}
              </div>
              <h3>Phase receipts</h3>
              <ol className="phase-timeline">
                {result.phase_receipts.map((receipt) => <li key={receipt.artifact_id} className={`phase-${text(receipt.payload.status)}`}>
                  <span>{text(receipt.payload.phase_key)}</span><strong>{text(receipt.payload.status)}</strong><Link to={`/artifacts/${receipt.artifact_id}`}>Artifact</Link>
                </li>)}
              </ol>
              <h3>Oracle evaluations</h3>
              <div className="oracle-list">{oracleEvaluations.map((item) => <div key={text(item.oracle_key)}><span className={`badge oracle-${text(item.status)}`}>{text(item.status)}</span><strong>{text(item.oracle_key)}</strong><p>{text(item.explanation)}</p></div>)}</div>
            </>}
          </article>

          <article className="panel">
            <h2>Canonical instance preview</h2>
            <JsonTree value={{ template_key: templateKey, binding_key: bindingKey, variant_key: variant, seed, parameter_bindings: { scale_profile: scaleProfile, tenant_skew: tenantSkew, parent_count: parentCount, relation_fanout: relationFanout, batch_size: batchSize, page_offset: pageOffset, transaction_scope: transactionScope }, applied_mutations: mutations }} />
          </article>

          <article className="panel">
            <h2>Recent scenario runs</h2>
            <div className="recent-run-list">{runs.map((item) => <Link className="recent-run-row" key={item.artifact_id} to={`/artifacts/${item.artifact_id}`}><span><strong>{item.title ?? item.artifact_id}</strong><code>{item.artifact_id}</code></span><span>{item.status ?? "unknown"}</span></Link>)}</div>
          </article>
        </div>
      </div>
    </section>
  );
}
