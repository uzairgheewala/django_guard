import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { JsonTree } from "../components/JsonTree";
import {
  evaluateUniverseCoverage,
  generateRepresentatives,
  getUniverseCatalog,
  listCoverageReports,
  type ArtifactDocumentLike,
  type IndexedArtifactSummary,
  type RepresentativeSetResponse,
  type UniverseCatalogResponse,
} from "../lib/api";

function text(value: unknown, fallback = "unknown"): string {
  return typeof value === "string" ? value : fallback;
}

function object(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function rows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object")) : [];
}

const defaultStrategies = ["axis-partitions.v1", "high-risk-pairwise.v1", "mutation-coverage.v1"];

export function UniverseExplorerPage() {
  const [catalog, setCatalog] = useState<UniverseCatalogResponse | null>(null);
  const [reports, setReports] = useState<IndexedArtifactSummary[]>([]);
  const [representatives, setRepresentatives] = useState<RepresentativeSetResponse | null>(null);
  const [coverage, setCoverage] = useState<ArtifactDocumentLike | null>(null);
  const [maximumCases, setMaximumCases] = useState(24);
  const [seed, setSeed] = useState(1);
  const [strategies, setStrategies] = useState<string[]>(defaultStrategies);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshReports = () => listCoverageReports(12).then((response) => setReports(response.items));

  useEffect(() => {
    getUniverseCatalog().then(setCatalog).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)));
    refreshReports().catch(() => undefined);
  }, []);

  const universe = catalog?.universes[0] ?? null;
  const availableStrategies = useMemo(() => rows(universe?.payload.strategies), [universe]);

  const toggleStrategy = (key: string) => {
    setStrategies((current) => current.includes(key) ? current.filter((item) => item !== key) : [...current, key]);
  };

  const generate = async () => {
    if (!universe) return;
    setBusy("generate");
    setError(null);
    try {
      const response = await generateRepresentatives(universe.artifact_id, { maximum_cases: maximumCases, seed, strategy_keys: strategies });
      setRepresentatives(response);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(null);
    }
  };

  const evaluate = async () => {
    if (!universe) return;
    setBusy("evaluate");
    setError(null);
    try {
      const response = await evaluateUniverseCoverage(universe.artifact_id, {
        representative_set_id: representatives?.representative_set.artifact_id,
        scenario_instance_ids: representatives?.instances.map((item) => item.artifact_id),
      });
      setCoverage(response);
      await refreshReports();
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(null);
    }
  };

  if (!catalog && !error) return <p className="empty-state">Loading declared universes…</p>;
  if (!universe) return <div className="error-banner" role="alert">{error ?? "No universe profile is available."}</div>;

  const axes = rows(universe.payload.axes);
  const constraints = rows(universe.payload.constraints);
  const statusCounts = object(coverage?.payload.status_counts);
  const dimensions = rows(coverage?.payload.dimension_coverage);
  const interactions = rows(coverage?.payload.interaction_coverage);
  const cells = rows(coverage?.payload.cells);
  const selectionRows = rows(representatives?.representative_set.payload.selections);

  return (
    <section>
      <header className="page-header">
        <div>
          <p className="eyebrow">Declared behavior space</p>
          <h1>Universe Explorer</h1>
          <p>Generate representative scenario instances from constrained axes, then trace each coverage claim back to canonical instances and runs.</p>
        </div>
        <Link className="secondary-button" to={`/artifacts/${universe.artifact_id}`}>Inspect profile artifact</Link>
      </header>
      {error && <div className="error-banner" role="alert">{error}</div>}

      <div className="metric-grid four-up">
        <div className="metric-card"><span>Axes</span><strong>{axes.length}</strong></div>
        <div className="metric-card"><span>Constraints</span><strong>{constraints.length}</strong></div>
        <div className="metric-card"><span>Strategies</span><strong>{availableStrategies.length}</strong></div>
        <div className="metric-card"><span>Templates</span><strong>{Array.isArray(universe.payload.template_refs) ? universe.payload.template_refs.length : 0}</strong></div>
      </div>

      <div className="universe-layout">
        <div className="universe-controls">
          <article className="panel">
            <h2>{text(universe.payload.title)}</h2>
            <p>{text(universe.payload.description)}</p>
            <div className="axis-list">
              {axes.map((axis) => {
                const domain = object(axis.domain);
                const values = Array.isArray(domain.values) ? domain.values : [];
                const partitions = rows(domain.partitions);
                return <div key={text(axis.axis_key)}>
                  <strong>{text(axis.title)}</strong>
                  <code>{text(axis.axis_key)}</code>
                  <small>{values.length ? values.join(", ") : partitions.map((item) => text(item.key)).join(", ")}</small>
                </div>;
              })}
            </div>
          </article>

          <article className="panel">
            <h2>Representative-set builder</h2>
            <div className="scenario-form-grid">
              <label>Maximum cases<input type="number" min={1} max={100} value={maximumCases} onChange={(event) => setMaximumCases(Number(event.target.value))} /></label>
              <label>Generation seed<input type="number" value={seed} onChange={(event) => setSeed(Number(event.target.value))} /></label>
            </div>
            <div className="strategy-list">
              {availableStrategies.map((strategy) => {
                const key = text(strategy.strategy_key);
                return <label className="mutation-row" key={key}>
                  <input type="checkbox" checked={strategies.includes(key)} onChange={() => toggleStrategy(key)} />
                  <span><strong>{key}</strong><small>{text(strategy.kind)} · {Array.isArray(strategy.dimensions) ? strategy.dimensions.join(", ") : ""}</small></span>
                </label>;
              })}
            </div>
            <div className="result-links">
              <button className="primary-button" type="button" disabled={Boolean(busy) || strategies.length === 0} onClick={generate}>{busy === "generate" ? "Generating…" : "Generate representatives"}</button>
              <button className="secondary-button" type="button" disabled={Boolean(busy)} onClick={evaluate}>{busy === "evaluate" ? "Evaluating…" : "Evaluate coverage"}</button>
            </div>
          </article>
        </div>

        <div className="universe-results">
          <article className="panel">
            <h2>Representative set</h2>
            {!representatives && <p className="empty-state">Generate a bounded representative set to see marginal coverage contribution.</p>}
            {representatives && <>
              <div className="metric-grid three-up">
                <div className="metric-card"><span>Selected</span><strong>{selectionRows.length}</strong></div>
                <div className="metric-card"><span>Covered cells</span><strong>{Array.isArray(representatives.representative_set.payload.covered_cell_keys) ? representatives.representative_set.payload.covered_cell_keys.length : 0}</strong></div>
                <div className="metric-card"><span>Remaining</span><strong>{Array.isArray(representatives.representative_set.payload.uncovered_cell_keys) ? representatives.representative_set.payload.uncovered_cell_keys.length : 0}</strong></div>
              </div>
              <div className="representative-list">
                {selectionRows.slice(0, 16).map((selection, index) => {
                  const ref = object(selection.scenario_instance_ref);
                  return <div key={text(ref.artifact_id, String(index))}>
                    <span><strong>Case {index + 1}</strong><code>{text(ref.artifact_id)}</code></span>
                    <span>{String(selection.marginal_coverage ?? 0)} cells</span>
                    <Link to={`/artifacts/${text(ref.artifact_id)}`}>Inspect</Link>
                  </div>;
                })}
              </div>
            </>}
          </article>

          <article className="panel">
            <h2>Coverage ledger</h2>
            {!coverage && <p className="empty-state">Evaluate the current scenario corpus or the generated representative set.</p>}
            {coverage && <>
              <div className="coverage-status-grid">
                {["covered", "uncovered", "inapplicable", "unsupported", "unknown"].map((key) => <div className={`coverage-status coverage-${key}`} key={key}><span>{key}</span><strong>{String(statusCounts[key] ?? 0)}</strong></div>)}
              </div>
              <h3>Dimension coverage</h3>
              <div className="dimension-coverage-list">
                {dimensions.map((item) => <div key={text(item.axis_key)}>
                  <strong>{text(item.axis_key)}</strong>
                  <span>{Array.isArray(item.covered_values) ? item.covered_values.length : 0} covered</span>
                  <small>Missing: {Array.isArray(item.uncovered_values) ? item.uncovered_values.join(", ") || "none" : "none"}</small>
                </div>)}
              </div>
              <h3>Interaction coverage</h3>
              <div className="interaction-list">
                {interactions.map((item) => <div key={text(item.strategy_key)}><span><strong>{text(item.strategy_key)}</strong><small>{String(item.covered ?? 0)} / {String(item.total ?? 0)}</small></span><progress max={1} value={typeof item.ratio === "number" ? item.ratio : 0} /></div>)}
              </div>
              <details><summary>Coverage cells ({cells.length})</summary><JsonTree value={cells.slice(0, 100)} /></details>
              <Link className="secondary-button" to={`/artifacts/${coverage.artifact_id}`}>Inspect coverage artifact</Link>
            </>}
          </article>
        </div>
      </div>

      <article className="panel recent-runs-panel">
        <h2>Recent coverage reports</h2>
        {!reports.length && <p className="empty-state">No persisted reports yet.</p>}
        <div className="recent-run-list">{reports.map((item) => <Link className="recent-run-row" key={item.artifact_id} to={`/artifacts/${item.artifact_id}`}><span><strong>{item.title ?? "Coverage report"}</strong><code>{item.artifact_id}</code></span><span>{item.status ?? "evaluated"}</span></Link>)}</div>
      </article>
    </section>
  );
}
