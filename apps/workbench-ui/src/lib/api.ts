import type { MaterializedArtifact, ArtifactSummary } from "../generated/artifact-types";

const API_BASE = import.meta.env.VITE_PLANGUARD_API_BASE ?? "http://127.0.0.1:8000";

export interface ArtifactListResponse {
  items: ArtifactSummary[];
  count: number;
}

export interface CapabilitiesResponse {
  capabilities: Record<string, "supported" | "partial" | "unsupported" | "unknown">;
  contracts: Array<{ artifact_kind: string; schema_version: string }>;
  extension_namespaces: string[];
  family_schemes?: string[];
  detectors?: string[];
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

export function listArtifacts(kind?: string): Promise<ArtifactListResponse> {
  const query = kind ? `?kind=${encodeURIComponent(kind)}` : "";
  return request(`/api/v1/artifacts${query}`);
}

export function getArtifact(artifactId: string): Promise<MaterializedArtifact> {
  return request(`/api/v1/artifacts/${encodeURIComponent(artifactId)}`);
}

export function verifyArtifact(
  artifactId: string,
): Promise<{ artifact_id: string; verified: boolean }> {
  return request(`/api/v1/artifacts/${encodeURIComponent(artifactId)}/integrity`);
}

export function getCapabilities(): Promise<CapabilitiesResponse> {
  return request("/api/v1/capabilities");
}

export function importArtifact(rawJson: string): Promise<ArtifactSummary> {
  return request("/api/v1/import", { method: "POST", body: rawJson });
}

export function listRuns(): Promise<RunListResponse> {
  return request("/api/v1/runs");
}

export function getRun(runId: string): Promise<RunDetailResponse> {
  return request(`/api/v1/runs/${encodeURIComponent(runId)}`);
}

export function evaluateRunPolicy(
  runId: string,
  policyPayload: Record<string, unknown>,
): Promise<ArtifactDocumentLike> {
  return request(`/api/v1/runs/${encodeURIComponent(runId)}/policy-evaluations`, {
    method: "POST",
    body: JSON.stringify({ policy_payload: policyPayload }),
  });
}
