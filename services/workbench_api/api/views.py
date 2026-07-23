from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from planguard.analysis.load import load_analysis_bundle
from planguard.artifacts.codec import default_codec
from planguard.artifacts.models import (
    BudgetPolicyArtifact,
    BudgetPolicyPayload,
    ProducerIdentity,
    RunManifestArtifact,
)
from planguard.canonical import canonical_data
from planguard.errors import PlanGuardError
from planguard.policy.engine import evaluate_policy
from planguard.store.filesystem import FilesystemArtifactStore


@lru_cache(maxsize=1)
def artifact_store() -> FilesystemArtifactStore:
    return FilesystemArtifactStore(settings.PLANGUARD_STORE)


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


def _artifact_summary(record) -> dict[str, Any]:
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
            "milestone": "B",
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
                "artifact.extensions": "supported",
                "query.capture.django": "supported",
                "query.normalization": "partial",
                "query.family": "supported",
                "analysis.detectors": "supported",
                "policy.absolute": "supported",
                "pytest.integration": "supported",
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
        }
    )


@require_GET
def artifacts(request: HttpRequest) -> JsonResponse:
    kind = request.GET.get("kind") or None
    records = artifact_store().list(artifact_kind=kind)
    return JsonResponse({"items": [_artifact_summary(record) for record in records], "count": len(records)})


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
        {
            "artifact_id": artifact_id,
            "verified": artifact_store().verify(artifact_id),
        }
    )


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
    except Exception as exc:
        return _error_response(exc, status=400)
    return JsonResponse(_artifact_summary(record), status=201)


@require_GET
def runs(request: HttpRequest) -> JsonResponse:
    items: list[dict[str, Any]] = []
    for record in artifact_store().list(artifact_kind="run_manifest"):
        artifact = artifact_store().load(record.artifact_id)
        if not isinstance(artifact, RunManifestArtifact):
            continue
        run = artifact.payload.run
        items.append(
            {
                **_artifact_summary(record),
                "name": run.name,
                "mode": run.mode,
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "tags": list(run.tags),
                "inventory": canonical_data(artifact.payload.artifact_inventory),
            }
        )
    items.sort(key=lambda item: item["created_at"], reverse=True)
    return JsonResponse({"items": items, "count": len(items)})


def _bundle_payload(run_id: str) -> dict[str, Any]:
    manifest, bundle = load_analysis_bundle(artifact_store(), run_id)
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
        _, bundle = load_analysis_bundle(artifact_store(), run_id)
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
        _, bundle = load_analysis_bundle(artifact_store(), run_id)
        return JsonResponse(
            {"items": [canonical_data(item) for item in bundle.findings], "count": len(bundle.findings)}
        )
    except Exception as exc:
        return _error_response(exc, status=404)


@csrf_exempt
@require_http_methods(["POST"])
def evaluate_run_policy(request: HttpRequest, run_id: str) -> JsonResponse:
    try:
        _, bundle = load_analysis_bundle(artifact_store(), run_id)
        body = json.loads(request.body.decode("utf-8"))
        if "policy_artifact_id" in body:
            policy = artifact_store().load(body["policy_artifact_id"])
        elif "policy_payload" in body:
            policy = BudgetPolicyArtifact(
                producer=ProducerIdentity(
                    name="planguard", version="0.2.0", build="workbench-api"
                ),
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
            producer=ProducerIdentity(name="planguard", version="0.2.0", build="workbench-api"),
        )
        artifact_store().save(evaluation)
        return JsonResponse(canonical_data(evaluation), status=201)
    except Exception as exc:
        return _error_response(exc, status=400)
