from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from planguard.analysis.load import load_analysis_bundle
from planguard.analysis.workload import build_workload
from planguard.artifacts.codec import default_codec
from planguard.artifacts.models import (
    BudgetPolicyArtifact,
    BudgetPolicyPayload,
    ProducerIdentity,
    RunManifestArtifact,
    WorkloadGraphArtifact,
)
from planguard.canonical import canonical_data
from planguard.errors import PlanGuardError
from planguard.policy.engine import evaluate_policy
from planguard.store.bundle import export_run_bundle
from planguard.store.filesystem import FilesystemArtifactStore
from planguard.store.index import ArtifactIndex


@lru_cache(maxsize=1)
def artifact_store() -> FilesystemArtifactStore:
    return FilesystemArtifactStore(settings.PLANGUARD_STORE)


@lru_cache(maxsize=1)
def artifact_index() -> ArtifactIndex:
    index = ArtifactIndex(settings.PLANGUARD_INDEX)
    index.sync(artifact_store())
    return index


def _sync_index() -> ArtifactIndex:
    """Return the startup-synchronized index without rescanning canonical storage."""
    return artifact_index()


def _error_response(exc: Exception, *, status: int = 400) -> JsonResponse:
    if isinstance(exc, PlanGuardError):
        payload: dict[str, Any] = {
            "error": exc.code,
            "message": exc.message,
            "details": exc.details,
        }
    else:
        payload = {"error": type(exc).__name__, "message": str(exc)}
    return JsonResponse(payload, status=status)


def _int_arg(request: HttpRequest, key: str, default: int) -> int:
    try:
        return int(request.GET.get(key, default))
    except (TypeError, ValueError):
        return default


def _artifact_summary(record: Any) -> dict[str, Any]:
    return {
        "artifact_id": record.artifact_id,
        "artifact_kind": record.artifact_kind,
        "schema_version": record.schema_version,
        "content_hash": record.content_hash,
        "created_at": record.created_at.isoformat(),
    }


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {
            "status": "ok",
            "service": "planguard-workbench-api",
            "milestone": "C",
            "mode": "explorer",
        }
    )


@require_GET
def capabilities(request: HttpRequest) -> JsonResponse:
    contracts = [
        {"artifact_kind": kind, "schema_version": version}
        for kind, version in default_codec.artifact_registry.keys()
    ]
    return JsonResponse(
        {
            "capabilities": {
                "artifact.read": "supported",
                "artifact.import": "supported",
                "artifact.integrity": "supported",
                "artifact.provenance": "supported",
                "artifact.search": "supported",
                "artifact.index.rebuild": "supported",
                "query.capture.django": "supported",
                "query.normalization": "partial",
                "query.family": "supported",
                "analysis.detectors": "supported",
                "policy.absolute": "supported",
                "pytest.integration": "supported",
                "workload.graph": "supported",
                "workload.motif": "supported",
                "workload.episode": "supported",
                "plan.postgresql": "unsupported",
                "scenario.execution": "unsupported",
            },
            "contracts": contracts,
            "extension_namespaces": list(default_codec.extension_registry.namespaces()),
            "family_schemes": [
                "exact-execution.v1",
                "structural-shape.v1",
                "shape-origin.v1",
                "shape-parameter-regime.v1",
            ],
            "detectors": [
                "exact-duplicate-execution.v1",
                "structural-repetition.v1",
                "likely-n-plus-one.v1",
                "slow-family-concentration.v1",
            ],
            "motifs": [
                "exact-duplicate-cluster.v1",
                "parameterized-repetition.v1",
                "parent-driven-repeated-lookup.v1",
                "per-item-write-loop.v1",
                "long-transaction-accumulation.v1",
            ],
        }
    )


@require_GET
def registry_stats(request: HttpRequest) -> JsonResponse:
    return JsonResponse(_sync_index().stats())


@csrf_exempt
@require_http_methods(["POST"])
def rebuild_registry(request: HttpRequest) -> JsonResponse:
    count = artifact_index().rebuild(artifact_store())
    return JsonResponse({"status": "rebuilt", "artifact_count": count})


@require_GET
def artifacts(request: HttpRequest) -> JsonResponse:
    page = _sync_index().search(
        query=request.GET.get("q") or None,
        artifact_kind=request.GET.get("kind") or None,
        run_id=request.GET.get("run_id") or None,
        tag=request.GET.get("tag") or None,
        status=request.GET.get("status") or None,
        mode=request.GET.get("mode") or None,
        mechanism_key=request.GET.get("mechanism") or None,
        severity=request.GET.get("severity") or None,
        motif_key=request.GET.get("motif") or None,
        limit=_int_arg(request, "limit", 50),
        offset=_int_arg(request, "offset", 0),
    )
    return JsonResponse(
        {
            "items": list(page.items),
            "count": len(page.items),
            "total": page.total,
            "limit": page.limit,
            "offset": page.offset,
        }
    )


@require_GET
def artifact_detail(request: HttpRequest, artifact_id: str) -> JsonResponse:
    try:
        artifact = artifact_store().load(artifact_id)
    except Exception as exc:
        return _error_response(exc, status=404)
    return JsonResponse(canonical_data(artifact), safe=True)


@require_GET
def artifact_integrity(request: HttpRequest, artifact_id: str) -> JsonResponse:
    return JsonResponse(
        {"artifact_id": artifact_id, "verified": artifact_store().verify(artifact_id)}
    )


@require_GET
def artifact_related(request: HttpRequest, artifact_id: str) -> JsonResponse:
    try:
        return JsonResponse(canonical_data(_sync_index().related(artifact_id)), safe=True)
    except Exception as exc:
        return _error_response(exc, status=404)


@csrf_exempt
@require_http_methods(["POST"])
def import_artifact(request: HttpRequest) -> JsonResponse:
    if not request.body:
        return JsonResponse(
            {"error": "empty_body", "message": "Expected one artifact JSON document"},
            status=400,
        )
    try:
        json.loads(request.body.decode("utf-8"))
        record = artifact_store().import_bytes(request.body)
        artifact_index().upsert(artifact_store().load(record.artifact_id))
    except Exception as exc:
        return _error_response(exc, status=400)
    return JsonResponse(_artifact_summary(record), status=201)


@require_GET
def runs(request: HttpRequest) -> JsonResponse:
    index = _sync_index()
    page = index.search(
        query=request.GET.get("q") or None,
        artifact_kind="run_manifest",
        tag=request.GET.get("tag") or None,
        status=request.GET.get("status") or None,
        mode=request.GET.get("mode") or None,
        limit=_int_arg(request, "limit", 50),
        offset=_int_arg(request, "offset", 0),
    )
    items: list[dict[str, Any]] = []
    has_finding = request.GET.get("has_finding")
    for indexed in page.items:
        artifact = artifact_store().load(indexed["artifact_id"])
        if not isinstance(artifact, RunManifestArtifact):
            continue
        if has_finding:
            finding_page = index.search(
                artifact_kind="finding",
                run_id=artifact.artifact_id,
                mechanism_key=None if has_finding in {"1", "true"} else has_finding,
                limit=1,
            )
            if finding_page.total == 0:
                continue
        run = artifact.payload.run
        items.append(
            {
                "artifact_id": artifact.artifact_id,
                "artifact_kind": artifact.artifact_kind,
                "schema_version": artifact.schema_version,
                "content_hash": artifact.content_hash,
                "created_at": artifact.created_at.isoformat(),
                "name": run.name,
                "mode": run.mode,
                "status": str(run.status),
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "tags": list(run.tags),
                "inventory": canonical_data(artifact.payload.artifact_inventory),
            }
        )
    return JsonResponse(
        {
            "items": items,
            "count": len(items),
            "total": page.total,
            "limit": page.limit,
            "offset": page.offset,
        }
    )


def _bundle_payload(run_id: str) -> dict[str, Any]:
    manifest, bundle = load_analysis_bundle(artifact_store(), run_id, index=_sync_index())
    return {
        "manifest": canonical_data(manifest),
        "summary": canonical_data(bundle.summary),
        "executions": [canonical_data(item) for item in bundle.executions],
        "templates": [canonical_data(item) for item in bundle.templates],
        "families": [canonical_data(item) for item in bundle.families],
        "evidence": [canonical_data(item) for item in bundle.evidence],
        "findings": [canonical_data(item) for item in bundle.findings],
        "detector_receipts": [canonical_data(item) for item in bundle.detector_receipts],
        "budget_evaluations": [canonical_data(item) for item in bundle.budget_evaluations],
        "workload_graphs": [canonical_data(item) for item in bundle.workload_graphs],
        "workload_motifs": [canonical_data(item) for item in bundle.workload_motifs],
        "workload_episodes": [canonical_data(item) for item in bundle.workload_episodes],
    }


@require_GET
def run_detail(request: HttpRequest, run_id: str) -> JsonResponse:
    try:
        return JsonResponse(_bundle_payload(run_id), safe=True)
    except Exception as exc:
        return _error_response(exc, status=404)


@require_GET
def run_families(request: HttpRequest, run_id: str) -> JsonResponse:
    try:
        _, bundle = load_analysis_bundle(artifact_store(), run_id, index=_sync_index())
        scheme = request.GET.get("scheme")
        items = [
            item for item in bundle.families if not scheme or item.payload.family_scheme_key == scheme
        ]
        return JsonResponse({"items": [canonical_data(item) for item in items], "count": len(items)})
    except Exception as exc:
        return _error_response(exc, status=404)


@require_GET
def run_findings(request: HttpRequest, run_id: str) -> JsonResponse:
    try:
        _, bundle = load_analysis_bundle(artifact_store(), run_id, index=_sync_index())
        return JsonResponse(
            {"items": [canonical_data(item) for item in bundle.findings], "count": len(bundle.findings)}
        )
    except Exception as exc:
        return _error_response(exc, status=404)


@require_GET
def run_graph(request: HttpRequest, run_id: str) -> JsonResponse:
    try:
        _, bundle = load_analysis_bundle(artifact_store(), run_id, index=_sync_index())
        scheme = request.GET.get("scheme") or "shape-origin.v1"
        graph = next(
            (item for item in bundle.workload_graphs if item.payload.family_scheme_key == scheme),
            None,
        )
        episodes = tuple(
            item for item in bundle.workload_episodes if item.payload.family_scheme_key == scheme
        )
        if graph is None:
            built = build_workload(
                run_id=run_id,
                executions=bundle.executions,
                templates=bundle.templates,
                families=bundle.families,
                findings=bundle.findings,
                producer=ProducerIdentity(name="planguard", version="0.3.0", build="workbench-api"),
                family_scheme_key=scheme,
            )
            graph = built.graph
            episodes = built.episodes
            if request.GET.get("persist") in {"1", "true"}:
                artifact_store().save(graph)
                for motif in built.motifs:
                    artifact_store().save(motif)
                for episode in built.episodes:
                    artifact_store().save(episode)
                _sync_index()
        return JsonResponse(
            {
                "graph": canonical_data(graph),
                "episodes": [canonical_data(item) for item in episodes],
            },
            safe=True,
        )
    except Exception as exc:
        return _error_response(exc, status=404)


@require_GET
def run_episodes(request: HttpRequest, run_id: str) -> JsonResponse:
    try:
        _, bundle = load_analysis_bundle(artifact_store(), run_id, index=_sync_index())
        motif = request.GET.get("motif")
        scheme = request.GET.get("scheme")
        items = [
            item
            for item in bundle.workload_episodes
            if (not motif or item.payload.motif_key == motif)
            and (not scheme or item.payload.family_scheme_key == scheme)
        ]
        return JsonResponse({"items": [canonical_data(item) for item in items], "count": len(items)})
    except Exception as exc:
        return _error_response(exc, status=404)


@require_GET
def motifs(request: HttpRequest) -> JsonResponse:
    page = _sync_index().search(artifact_kind="workload_motif", limit=100)
    items = [canonical_data(artifact_store().load(item["artifact_id"])) for item in page.items]
    return JsonResponse({"items": items, "count": len(items)})


@require_GET
def export_run(request: HttpRequest, run_id: str) -> HttpResponse:
    try:
        raw = export_run_bundle(artifact_store(), run_id)
    except Exception as exc:
        return _error_response(exc, status=404)
    response = HttpResponse(raw, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{run_id}.planguard.zip"'
    return response


@csrf_exempt
@require_http_methods(["POST"])
def evaluate_run_policy(request: HttpRequest, run_id: str) -> JsonResponse:
    try:
        _, bundle = load_analysis_bundle(artifact_store(), run_id, index=_sync_index())
        body = json.loads(request.body.decode("utf-8"))
        if "policy_artifact_id" in body:
            policy = artifact_store().load(body["policy_artifact_id"])
        elif "policy_payload" in body:
            policy = BudgetPolicyArtifact(
                producer=ProducerIdentity(name="planguard", version="0.3.0", build="workbench-api"),
                payload=BudgetPolicyPayload.model_validate(body["policy_payload"]),
            ).seal()
            artifact_store().save(policy)
        else:
            policy = default_codec.decode(body.get("policy", body))
        if not isinstance(policy, BudgetPolicyArtifact):
            raise ValueError("Request must identify or contain a budget_policy artifact")
        evaluation = evaluate_policy(
            bundle,
            policy,
            producer=ProducerIdentity(name="planguard", version="0.3.0", build="workbench-api"),
        )
        artifact_store().save(evaluation)
        _sync_index()
        return JsonResponse(canonical_data(evaluation), status=201)
    except Exception as exc:
        return _error_response(exc, status=400)
