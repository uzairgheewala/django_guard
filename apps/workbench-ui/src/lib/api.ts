import type { MaterializedArtifact, ArtifactSummary } from "../generated/artifact-types";

const API_BASE = import.meta.env.VITE_PLANGUARD_API_BASE ?? "http://127.0.0.1:8000";

export interface IndexedArtifactSummary extends ArtifactSummary {
  run_id?: string | null;
  name?: string | null;
  mode?: string | null;
  status?: string | null;
  title?: string | null;
  mechanism_key?: string | null;
  severity?: string | null;
  confidence?: string | null;
  family_scheme_key?: string | null;
  query_shape_fingerprint?: string | null;
  motif_key?: string | null;
  metadata?: Record<string, unknown>;
}

export interface ArtifactListResponse {
  items: IndexedArtifactSummary[];
  count: number;
  total: number;
  limit: number;
  offset: number;
}

export interface CapabilitiesResponse {
  capabilities: Record<string, "supported" | "partial" | "unsupported" | "unknown">;
  contracts: Array<{ artifact_kind: string; schema_version: string }>;
  extension_namespaces: string[];
  family_schemes?: string[];
  detectors?: string[];
  motifs?: string[];
}

export interface RegistryStats {
  total_artifacts: number;
  runs: number;
  findings: number;
  episodes: number;
  scenarios?: number;
  scenario_templates?: number;
  by_kind: Record<string, number>;
}

export interface RunListItem extends ArtifactSummary {
  name: string;
  mode: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  tags: string[];
  inventory: { by_kind: Record<string, number>; total_count: number };
}

export interface RunListResponse {
  items: RunListItem[];
  count: number;
  total: number;
  limit: number;
  offset: number;
}

export interface ArtifactDocumentLike {
  artifact_id: string;
  artifact_kind: string;
  schema_version: string;
  created_at: string;
  content_hash: string;
  payload: Record<string, unknown>;
  provenance: Record<string, unknown>;
  extensions: Record<string, Record<string, unknown>>;
}

export interface RunDetailResponse {
  manifest: ArtifactDocumentLike;
  summary: ArtifactDocumentLike;
  executions: ArtifactDocumentLike[];
  templates: ArtifactDocumentLike[];
  families: ArtifactDocumentLike[];
  evidence: ArtifactDocumentLike[];
  findings: ArtifactDocumentLike[];
  detector_receipts: ArtifactDocumentLike[];
  budget_evaluations: ArtifactDocumentLike[];
  workload_graphs: ArtifactDocumentLike[];
  workload_motifs: ArtifactDocumentLike[];
  workload_episodes: ArtifactDocumentLike[];
}

export interface RunGraphResponse {
  graph: ArtifactDocumentLike;
  episodes: ArtifactDocumentLike[];
}

export interface RelatedArtifactsResponse {
  inputs: IndexedArtifactSummary[];
  derived: IndexedArtifactSummary[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = typeof body.message === "string" ? body.message : `HTTP ${response.status}`;
    throw new Error(message);
  }
  return body as T;
}

function queryString(values: Record<string, string | number | boolean | undefined>): string {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== "" && value !== false) params.set(key, String(value));
  });
  const rendered = params.toString();
  return rendered ? `?${rendered}` : "";
}

export function listArtifacts(filters: {
  kind?: string;
  q?: string;
  runId?: string;
  tag?: string;
  mechanism?: string;
  severity?: string;
  motif?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<ArtifactListResponse> {
  return request(`/api/v1/artifacts${queryString({
    kind: filters.kind,
    q: filters.q,
    run_id: filters.runId,
    tag: filters.tag,
    mechanism: filters.mechanism,
    severity: filters.severity,
    motif: filters.motif,
    limit: filters.limit,
    offset: filters.offset,
  })}`);
}

export function getArtifact(artifactId: string): Promise<MaterializedArtifact> {
  return request(`/api/v1/artifacts/${encodeURIComponent(artifactId)}`);
}

export function getRelatedArtifacts(artifactId: string): Promise<RelatedArtifactsResponse> {
  return request(`/api/v1/artifacts/${encodeURIComponent(artifactId)}/related`);
}

export function verifyArtifact(artifactId: string): Promise<{ artifact_id: string; verified: boolean }> {
  return request(`/api/v1/artifacts/${encodeURIComponent(artifactId)}/integrity`);
}

export function getCapabilities(): Promise<CapabilitiesResponse> {
  return request("/api/v1/capabilities");
}

export function getRegistryStats(): Promise<RegistryStats> {
  return request("/api/v1/registry/stats");
}

export function rebuildRegistry(): Promise<{ status: string; artifact_count: number }> {
  return request("/api/v1/registry/rebuild", { method: "POST", body: "{}" });
}

export function importArtifact(rawJson: string): Promise<ArtifactSummary> {
  return request("/api/v1/import", { method: "POST", body: rawJson });
}

export function listRuns(filters: {
  q?: string;
  status?: string;
  mode?: string;
  tag?: string;
  hasFinding?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<RunListResponse> {
  return request(`/api/v1/runs${queryString({
    q: filters.q,
    status: filters.status,
    mode: filters.mode,
    tag: filters.tag,
    has_finding: filters.hasFinding,
    limit: filters.limit,
    offset: filters.offset,
  })}`);
}

export function getRun(runId: string): Promise<RunDetailResponse> {
  return request(`/api/v1/runs/${encodeURIComponent(runId)}`);
}

export function getRunGraph(runId: string, scheme: string, persist = false): Promise<RunGraphResponse> {
  return request(`/api/v1/runs/${encodeURIComponent(runId)}/graph${queryString({ scheme, persist })}`);
}

export function runExportUrl(runId: string): string {
  return `${API_BASE}/api/v1/runs/${encodeURIComponent(runId)}/export`;
}

export function evaluateRunPolicy(runId: string, policyPayload: Record<string, unknown>): Promise<ArtifactDocumentLike> {
  return request(`/api/v1/runs/${encodeURIComponent(runId)}/policy-evaluations`, {
    method: "POST",
    body: JSON.stringify({ policy_payload: policyPayload }),
  });
}

export interface ScenarioCatalogResponse {
  templates: ArtifactDocumentLike[];
  bindings: ArtifactDocumentLike[];
  mutations: ArtifactDocumentLike[];
  execution_enabled: boolean;
}

export interface ScenarioExecutionResponse {
  scenario_run: ArtifactDocumentLike;
  phase_receipts: ArtifactDocumentLike[];
  dataset_manifest: ArtifactDocumentLike | null;
  analysis_run_id: string | null;
}

export interface ScenarioRunListResponse {
  items: IndexedArtifactSummary[];
  total: number;
  limit: number;
  offset: number;
}

export function getScenarioCatalog(): Promise<ScenarioCatalogResponse> {
  return request("/api/v1/scenarios/catalog");
}

export function listScenarioRuns(filters: { q?: string; status?: string; limit?: number; offset?: number } = {}): Promise<ScenarioRunListResponse> {
  return request(`/api/v1/scenarios/runs${queryString({ q: filters.q, status: filters.status, limit: filters.limit, offset: filters.offset })}`);
}

export function instantiateScenario(payload: Record<string, unknown>): Promise<ArtifactDocumentLike> {
  return request("/api/v1/scenarios/instances", { method: "POST", body: JSON.stringify(payload) });
}

export function executeScenario(payload: Record<string, unknown>): Promise<ScenarioExecutionResponse> {
  return request("/api/v1/scenarios/run", { method: "POST", body: JSON.stringify(payload) });
}

export function getScenarioRun(scenarioRunId: string): Promise<{
  scenario_run: ArtifactDocumentLike;
  scenario_instance: ArtifactDocumentLike;
  phase_receipts: ArtifactDocumentLike[];
  dataset_manifest: ArtifactDocumentLike | null;
}> {
  return request(`/api/v1/scenarios/runs/${encodeURIComponent(scenarioRunId)}`);
}
