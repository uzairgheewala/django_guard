"""Query template derivation and family projection."""

from __future__ import annotations

import hashlib
import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from planguard.artifacts.models import (
    ArtifactReference,
    FamilyAggregates,
    FamilySchemeArtifact,
    FamilySchemePayload,
    FamilyTemporalRange,
    ObservedQueryFamilyArtifact,
    ObservedQueryFamilyPayload,
    ParameterRegime,
    ProducerIdentity,
    Provenance,
    QueryExecutionArtifact,
    QueryTemplateArtifact,
    QueryTemplatePayload,
)
from planguard.canonical import canonical_json_bytes
from planguard.ids import content_derived_id
from planguard.analysis.normalize import normalize_sql, parameter_regime


@dataclass(frozen=True, slots=True)
class FamilySchemeDefinition:
    key: str
    title: str
    dimensions: tuple[str, ...]
    description: str


BUILTIN_SCHEMES: tuple[FamilySchemeDefinition, ...] = (
    FamilySchemeDefinition(
        "exact-execution.v1",
        "Exact execution",
        ("query.shape", "parameters.binding", "origin.frame"),
        "Groups identical structural queries with identical parameter bindings and origin.",
    ),
    FamilySchemeDefinition(
        "structural-shape.v1",
        "Structural shape",
        ("query.shape",),
        "Groups all executions sharing the conservative structural SQL fingerprint.",
    ),
    FamilySchemeDefinition(
        "shape-origin.v1",
        "Shape and origin",
        ("query.shape", "origin.frame"),
        "Separates structurally identical queries by their first application call site.",
    ),
    FamilySchemeDefinition(
        "shape-parameter-regime.v1",
        "Shape and parameter regime",
        ("query.shape", "parameters.regime"),
        "Separates a query shape by scalar/list parameter behavior.",
    ),
)


def _hash(prefix: str, value: Any) -> str:
    return f"{prefix}_{hashlib.sha256(canonical_json_bytes(value)).hexdigest()}"


def builtin_scheme_artifacts(producer: ProducerIdentity) -> tuple[FamilySchemeArtifact, ...]:
    artifacts: list[FamilySchemeArtifact] = []
    for definition in BUILTIN_SCHEMES:
        payload = FamilySchemePayload(
            family_scheme_key=definition.key,
            title=definition.title,
            dimensions=definition.dimensions,
            description=definition.description,
        )
        artifacts.append(FamilySchemeArtifact(producer=producer, payload=payload))
    return tuple(artifacts)


def derive_templates(
    executions: Iterable[QueryExecutionArtifact],
    *,
    producer: ProducerIdentity,
) -> tuple[dict[str, QueryTemplateArtifact], dict[str, QueryTemplateArtifact]]:
    by_execution: dict[str, QueryTemplateArtifact] = {}
    by_shape: dict[str, QueryTemplateArtifact] = {}
    for execution in executions:
        sql = execution.payload.sql or ""
        normalized = normalize_sql(sql, dialect=execution.payload.connection.vendor)
        template = by_shape.get(normalized.structural_shape_fingerprint)
        if template is None:
            payload = QueryTemplatePayload(
                dialect=execution.payload.connection.vendor,
                canonical_sql=normalized.canonical_sql,
                lexical_fingerprint=normalized.lexical_fingerprint,
                structural_shape_fingerprint=normalized.structural_shape_fingerprint,
                statement_kind=normalized.statement_kind,
                features=normalized.features,
                parse_quality=normalized.parse_quality,
                diagnostics=normalized.diagnostics,
            )
            template = QueryTemplateArtifact(
                producer=producer,
                provenance=Provenance(input_refs=(execution.reference(),), derivation_key="query-normalize.v1"),
                payload=payload,
            )
            by_shape[normalized.structural_shape_fingerprint] = template
        by_execution[execution.artifact_id] = template
    return by_execution, by_shape


def _origin_fingerprint(execution: QueryExecutionArtifact) -> str:
    origin = execution.payload.origin
    if origin.stack_fingerprint:
        return origin.stack_fingerprint
    frame = origin.application_frame
    if frame is None:
        return "unknown"
    return _hash(
        "frm",
        {
            "module": frame.module,
            "file": frame.file,
            "line": frame.line,
            "function": frame.function,
        },
    )


def dimension_value(
    dimension: str,
    execution: QueryExecutionArtifact,
    template: QueryTemplateArtifact,
) -> str:
    if dimension == "query.shape":
        return template.payload.structural_shape_fingerprint
    if dimension == "parameters.binding":
        return execution.payload.parameter_binding_fingerprint or "unknown"
    if dimension == "parameters.regime":
        return parameter_regime(execution.payload.parameters)
    if dimension == "origin.frame":
        return _origin_fingerprint(execution)
    if dimension == "connection.alias":
        return execution.payload.connection.alias
    if dimension == "operation.run":
        return execution.payload.run_id
    return f"unknown:{dimension}"


def project_families(
    executions: Iterable[QueryExecutionArtifact],
    templates_by_execution: dict[str, QueryTemplateArtifact],
    *,
    schemes: Iterable[FamilySchemeArtifact],
    producer: ProducerIdentity,
) -> tuple[ObservedQueryFamilyArtifact, ...]:
    execution_list = list(executions)
    if not execution_list:
        return ()
    run_id = execution_list[0].payload.run_id
    output: list[ObservedQueryFamilyArtifact] = []
    for scheme in schemes:
        groups: dict[tuple[str, ...], list[QueryExecutionArtifact]] = defaultdict(list)
        for execution in execution_list:
            template = templates_by_execution[execution.artifact_id]
            key = tuple(
                dimension_value(dimension, execution, template)
                for dimension in scheme.payload.dimensions
            )
            groups[key].append(execution)

        for key, members in groups.items():
            ordered = sorted(members, key=lambda item: item.payload.sequence_number)
            template = templates_by_execution[ordered[0].artifact_id]
            durations = [item.payload.timing.duration_ms for item in ordered]
            bindings = {
                item.payload.parameter_binding_fingerprint or "unknown" for item in ordered
            }
            regimes: dict[str, int] = defaultdict(int)
            for item in ordered:
                regimes[parameter_regime(item.payload.parameters)] += 1
            first = ordered[0].payload
            last = ordered[-1].payload
            values = dict(zip(scheme.payload.dimensions, key, strict=True))
            identity = {
                "run_id": run_id,
                "scheme": scheme.payload.family_scheme_key,
                "dimensions": values,
            }
            artifact_id = content_derived_id("qfam", canonical_json_bytes(identity), length=32)
            payload = ObservedQueryFamilyPayload(
                run_id=run_id,
                family_scheme_key=scheme.payload.family_scheme_key,
                query_template_ref=template.reference(),
                dimension_values=values,
                member_execution_refs=tuple(item.reference() for item in ordered),
                aggregates=FamilyAggregates(
                    execution_count=len(ordered),
                    distinct_parameter_bindings=len(bindings),
                    total_duration_ms=sum(durations),
                    mean_duration_ms=statistics.fmean(durations),
                    median_duration_ms=statistics.median(durations),
                    maximum_duration_ms=max(durations),
                    failed_execution_count=sum(
                        item.payload.outcome.status == "failed" for item in ordered
                    ),
                ),
                temporal=FamilyTemporalRange(
                    first_sequence=first.sequence_number,
                    last_sequence=last.sequence_number,
                    span_ms=max(
                        0.0,
                        (last.timing.started_offset_ms + last.timing.duration_ms)
                        - first.timing.started_offset_ms,
                    ),
                ),
                parameter_regimes=tuple(
                    ParameterRegime(regime_key=name, member_count=count)
                    for name, count in sorted(regimes.items())
                ),
            )
            output.append(
                ObservedQueryFamilyArtifact(
                    artifact_id=artifact_id,
                    producer=producer,
                    provenance=Provenance(
                        input_refs=tuple(item.reference() for item in ordered) + (scheme.reference(),),
                        derivation_key="query-family-project.v1",
                    ),
                    payload=payload,
                )
            )
    return tuple(sorted(output, key=lambda item: (item.payload.family_scheme_key, item.artifact_id)))
