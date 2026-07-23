"""Safety-first PostgreSQL EXPLAIN collection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, Sequence

from planguard.artifacts.models import (
    ArtifactReference,
    PlanCollectionContext,
    PlanCollectionMode,
    PlanCollectionReceiptArtifact,
    PlanCollectionReceiptPayload,
    PlanCollectionStatus,
    PlanObservationArtifact,
    PlanObservationPayload,
    ProducerIdentity,
    Provenance,
)
from planguard.postgres.normalize import normalize_postgres_plan
from planguard.time import utc_now

_READ_ONLY = re.compile(r"^\s*(select|with|values|show|table)\b", re.IGNORECASE)
_VOLATILE_HINT = re.compile(r"\b(nextval|setval|pg_advisory|dblink|lo_import|copy\s+)\b", re.IGNORECASE)


class CursorLike(Protocol):
    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any: ...
    def fetchone(self) -> Sequence[Any] | None: ...


class ConnectionLike(Protocol):
    vendor: str
    def cursor(self): ...


@dataclass(frozen=True, slots=True)
class PlanCollectionPolicy:
    mode: PlanCollectionMode = PlanCollectionMode.ESTIMATED_ONLY
    statement_timeout_ms: int = 2_000
    buffers: bool = True
    verbose: bool = False
    settings: bool = True
    wal: bool = False
    explicit_allowlist: frozenset[str] = frozenset()

    def safety_check(self, sql: str) -> tuple[bool, dict[str, Any], str | None]:
        normalized = sql.strip()
        checks = {
            "non_empty": bool(normalized),
            "read_only_shape": bool(_READ_ONLY.match(normalized)),
            "volatile_hint_absent": not bool(_VOLATILE_HINT.search(normalized)),
            "explicitly_allowlisted": normalized in self.explicit_allowlist,
        }
        if self.mode == PlanCollectionMode.DISABLED:
            return False, checks, "Plan collection is disabled"
        if not checks["non_empty"]:
            return False, checks, "SQL is empty"
        if self.mode in {PlanCollectionMode.ANALYZE_SAFE_SELECTS, PlanCollectionMode.EXPLICIT_ALLOWLIST}:
            if self.mode == PlanCollectionMode.EXPLICIT_ALLOWLIST and not checks["explicitly_allowlisted"]:
                return False, checks, "Statement is not explicitly allowlisted"
            if not checks["read_only_shape"]:
                return False, checks, "EXPLAIN ANALYZE is restricted to read-only statement shapes"
            if not checks["volatile_hint_absent"]:
                return False, checks, "Statement contains a potentially volatile operation"
        return True, checks, None


def _explain_sql(sql: str, policy: PlanCollectionPolicy) -> tuple[str, bool]:
    analyze = policy.mode in {PlanCollectionMode.ANALYZE_SAFE_SELECTS, PlanCollectionMode.EXPLICIT_ALLOWLIST}
    options = ["FORMAT JSON", f"ANALYZE {'TRUE' if analyze else 'FALSE'}"]
    if analyze:
        options.extend([
            f"BUFFERS {'TRUE' if policy.buffers else 'FALSE'}",
            f"WAL {'TRUE' if policy.wal else 'FALSE'}",
        ])
    options.extend([
        f"VERBOSE {'TRUE' if policy.verbose else 'FALSE'}",
        f"SETTINGS {'TRUE' if policy.settings else 'FALSE'}",
    ])
    return f"EXPLAIN ({', '.join(options)}) {sql}", analyze


def observation_from_raw_plan(
    *,
    raw_plan: Any,
    run_id: str,
    query_family_ref: ArtifactReference,
    producer: ProducerIdentity,
    representative_execution_ref: ArtifactReference | None = None,
    mode: PlanCollectionMode = PlanCollectionMode.IMPORTED,
    representative_strategy: str = "imported",
    statement_timeout_ms: int | None = None,
    cache_protocol: str = "unknown",
    server_version: str | None = None,
    database_settings: dict[str, Any] | None = None,
    parameter_regime_key: str | None = None,
    warnings: tuple[str, ...] = (),
) -> PlanObservationArtifact:
    root_id, nodes, features, metadata = normalize_postgres_plan(raw_plan)
    analyzed = any(node.actual_total_ms is not None for node in nodes)
    raw_object = raw_plan[0] if isinstance(raw_plan, list) and raw_plan else raw_plan
    return PlanObservationArtifact(
        producer=producer,
        provenance=Provenance(
            input_refs=tuple(ref for ref in (query_family_ref, representative_execution_ref) if ref),
            derivation_key="postgres-plan-normalize.v1",
        ),
        payload=PlanObservationPayload(
            run_id=run_id,
            query_family_ref=query_family_ref,
            representative_execution_ref=representative_execution_ref,
            parameter_regime_key=parameter_regime_key,
            collection=PlanCollectionContext(
                mode=mode,
                analyzed=analyzed,
                statement_timeout_ms=statement_timeout_ms,
                representative_strategy=representative_strategy,  # type: ignore[arg-type]
                cache_protocol=cache_protocol,  # type: ignore[arg-type]
                server_version=server_version,
                database_settings=database_settings or metadata.get("Settings", {}) or {},
            ),
            root_node_id=root_id,
            nodes=nodes,
            features=features,
            raw_plan=raw_object,
            warnings=warnings,
        ),
    ).seal()


def import_plan(
    *,
    raw_plan: Any,
    run_id: str,
    query_family_ref: ArtifactReference,
    producer: ProducerIdentity,
    representative_execution_ref: ArtifactReference | None = None,
    parameter_regime_key: str | None = None,
    cache_protocol: str = "unknown",
    server_version: str | None = None,
    database_settings: dict[str, Any] | None = None,
    warnings: tuple[str, ...] = (),
) -> tuple[PlanObservationArtifact, PlanCollectionReceiptArtifact]:
    started = utc_now()
    plan = observation_from_raw_plan(
        raw_plan=raw_plan, run_id=run_id, query_family_ref=query_family_ref,
        producer=producer, representative_execution_ref=representative_execution_ref,
        mode=PlanCollectionMode.IMPORTED, representative_strategy="imported",
        cache_protocol=cache_protocol, server_version=server_version,
        database_settings=database_settings, parameter_regime_key=parameter_regime_key,
        warnings=warnings,
    )
    receipt = PlanCollectionReceiptArtifact(
        producer=producer,
        provenance=Provenance(
            input_refs=tuple(ref for ref in (query_family_ref, representative_execution_ref) if ref),
            derivation_key="postgres-plan-import.v1",
        ),
        payload=PlanCollectionReceiptPayload(
            run_id=run_id, query_family_ref=query_family_ref,
            status=PlanCollectionStatus.COLLECTED, mode=PlanCollectionMode.IMPORTED,
            started_at=started, completed_at=utc_now(), plan_ref=plan.reference(),
            representative_execution_ref=representative_execution_ref,
            safety_checks={"source": "imported_json", "executed_sql": False},
            notes=("Imported plan normalization did not execute SQL.",),
        ),
    ).seal()
    return plan, receipt


def collect_plan(
    *,
    connection: ConnectionLike,
    sql: str,
    params: Sequence[Any] | None,
    run_id: str,
    query_family_ref: ArtifactReference,
    producer: ProducerIdentity,
    policy: PlanCollectionPolicy,
    representative_execution_ref: ArtifactReference | None = None,
    representative_strategy: str = "explicit",
) -> tuple[PlanObservationArtifact | None, PlanCollectionReceiptArtifact]:
    started = utc_now()
    allowed, checks, rejection = policy.safety_check(sql)
    if connection.vendor != "postgresql":
        allowed = False
        rejection = f"Connection vendor {connection.vendor!r} is not PostgreSQL"
        checks["postgresql_vendor"] = False
    else:
        checks["postgresql_vendor"] = True
    if not allowed:
        completed = utc_now()
        receipt = PlanCollectionReceiptArtifact(
            producer=producer,
            provenance=Provenance(input_refs=(query_family_ref,), derivation_key="postgres-plan-collect.v1"),
            payload=PlanCollectionReceiptPayload(
                run_id=run_id,
                query_family_ref=query_family_ref,
                status=PlanCollectionStatus.REJECTED,
                mode=policy.mode,
                started_at=started,
                completed_at=completed,
                representative_execution_ref=representative_execution_ref,
                safety_checks=checks,
                error=rejection,
            ),
        ).seal()
        return None, receipt
    try:
        explain_sql, analyzed = _explain_sql(sql, policy)
        with connection.cursor() as cursor:
            cursor.execute("SHOW statement_timeout")
            previous_timeout_row = cursor.fetchone()
            previous_timeout = str(previous_timeout_row[0]) if previous_timeout_row else "0"
            cursor.execute("SELECT set_config('statement_timeout', %s, false)", [f"{policy.statement_timeout_ms}ms"])
            try:
                cursor.execute(explain_sql, params)
                row = cursor.fetchone()
            finally:
                cursor.execute("SELECT set_config('statement_timeout', %s, false)", [previous_timeout])
        if not row:
            raise RuntimeError("EXPLAIN returned no row")
        plan = observation_from_raw_plan(
            raw_plan=row[0],
            run_id=run_id,
            query_family_ref=query_family_ref,
            representative_execution_ref=representative_execution_ref,
            producer=producer,
            mode=policy.mode,
            representative_strategy=representative_strategy,
            statement_timeout_ms=policy.statement_timeout_ms,
        )
        receipt = PlanCollectionReceiptArtifact(
            producer=producer,
            provenance=Provenance(input_refs=(query_family_ref,), derivation_key="postgres-plan-collect.v1"),
            payload=PlanCollectionReceiptPayload(
                run_id=run_id,
                query_family_ref=query_family_ref,
                status=PlanCollectionStatus.COLLECTED,
                mode=policy.mode,
                started_at=started,
                completed_at=utc_now(),
                plan_ref=plan.reference(),
                representative_execution_ref=representative_execution_ref,
                safety_checks={**checks, "analyzed": analyzed},
            ),
        ).seal()
        return plan, receipt
    except Exception as exc:
        receipt = PlanCollectionReceiptArtifact(
            producer=producer,
            provenance=Provenance(input_refs=(query_family_ref,), derivation_key="postgres-plan-collect.v1"),
            payload=PlanCollectionReceiptPayload(
                run_id=run_id,
                query_family_ref=query_family_ref,
                status=PlanCollectionStatus.FAILED,
                mode=policy.mode,
                started_at=started,
                completed_at=utc_now(),
                representative_execution_ref=representative_execution_ref,
                safety_checks=checks,
                error=f"{type(exc).__name__}: {exc}",
            ),
        ).seal()
        return None, receipt
