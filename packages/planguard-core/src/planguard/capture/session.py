"""Scoped query capture and run lifecycle.

The session supports manual recording for deterministic tests and laboratory
adapters. When Django is installed and configured, it attaches execution
wrappers to selected connections for the lifetime of the context manager.
"""

from __future__ import annotations

import contextvars
import os
import platform
import sys
import time
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Literal

from planguard.analysis.engine import AnalysisBundle, AnalysisEngine
from planguard.analysis.normalize import redact_sql
from planguard.artifacts.models import (
    ArtifactInventory,
    ArtifactReference,
    BudgetPolicyArtifact,
    BundleIntegrity,
    CapabilityState,
    CapabilityStatus,
    CapturePolicyArtifact,
    CapturePolicyPayload,
    DatabaseIdentity,
    EnvironmentProfileArtifact,
    EnvironmentProfilePayload,
    ParameterCaptureMode,
    ProducerIdentity,
    Provenance,
    QueryConnection,
    QueryExecutionArtifact,
    QueryExecutionPayload,
    QueryOutcome,
    QueryTiming,
    QueryTransaction,
    RawSqlMode,
    RunManifestArtifact,
    RunManifestPayload,
    RunStatus,
    RunSummary,
    RuntimeComponent,
)
from planguard.capture.origin import capture_origin
from planguard.capture.parameters import binding_fingerprint, capture_parameters
from planguard.ids import new_artifact_id
from planguard.policy.engine import QueryPolicy, evaluate_policy
from planguard.store.filesystem import FilesystemArtifactStore
from planguard.time import utc_now

_ACTIVE_SESSION: contextvars.ContextVar["AnalysisSession | None"] = contextvars.ContextVar(
    "planguard_active_session", default=None
)


@dataclass(frozen=True, slots=True)
class CapturedRun:
    manifest: RunManifestArtifact
    environment: EnvironmentProfileArtifact
    capture_policy: CapturePolicyArtifact
    analysis: AnalysisBundle


@dataclass(slots=True)
class _PendingExecution:
    sequence_number: int
    connection_alias: str
    vendor: str
    started_offset_ms: float
    duration_ms: float
    sql: str | None
    params: Any
    many: bool
    succeeded: bool
    exception: Exception | None
    origin: Any
    transaction_depth: int
    autocommit: bool | None
    row_count: int | None
    context: dict[str, Any] = field(default_factory=dict)


class AnalysisSession:
    def __init__(
        self,
        name: str,
        *,
        store: FilesystemArtifactStore | str | Path | None = None,
        mode: str = "function",
        tags: tuple[str, ...] = (),
        capture_policy: CapturePolicyPayload | None = None,
        producer: ProducerIdentity | None = None,
        hmac_key: bytes | None = None,
        analyze: bool = True,
        attach_django: bool = True,
        code_revision: str | None = None,
        budget_policy: BudgetPolicyArtifact | QueryPolicy | None = None,
        run_id: str | None = None,
        scenario_instance_ref: ArtifactReference | None = None,
    ) -> None:
        self.name = name
        self.mode = mode
        self.tags = tags
        self.run_id = run_id or new_artifact_id("run")
        self.store = (
            store
            if isinstance(store, FilesystemArtifactStore)
            else FilesystemArtifactStore(store or Path(".planguard"))
        )
        self.policy_payload = capture_policy or CapturePolicyPayload(
            policy_key="safe-local-default.v1",
            hmac_key_id="session-ephemeral",
        )
        self.producer = producer or ProducerIdentity(
            name="planguard", version="0.5.0", build="milestone-d"
        )
        self.hmac_key = hmac_key or os.urandom(32)
        self.analyze_enabled = analyze
        self.attach_django = attach_django
        self.code_revision = code_revision
        self.budget_policy = budget_policy
        self.scenario_instance_ref = scenario_instance_ref
        self._started_at: datetime | None = None
        self._completed_at: datetime | None = None
        self._start_clock: float | None = None
        self._token: contextvars.Token[AnalysisSession | None] | None = None
        self._exit_stack: ExitStack | None = None
        self._pending: list[_PendingExecution] = []
        self._limit_reached = False
        self.result: CapturedRun | None = None

    def __enter__(self) -> "AnalysisSession":
        if _ACTIVE_SESSION.get() is not None:
            raise RuntimeError("Nested PlanGuard capture sessions are not supported")
        self._started_at = utc_now()
        self._start_clock = time.perf_counter()
        self._token = _ACTIVE_SESSION.set(self)
        self._exit_stack = ExitStack()
        if self.attach_django:
            self._attach_django_wrappers(self._exit_stack)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        try:
            if self._exit_stack is not None:
                self._exit_stack.close()
            self._completed_at = utc_now()
            self.result = self._finalize(exc)
        finally:
            if self._token is not None:
                _ACTIVE_SESSION.reset(self._token)
        return False

    @property
    def analysis(self) -> AnalysisBundle:
        if self.result is None:
            raise RuntimeError("Capture session has not been finalized")
        return self.result.analysis

    @property
    def manifest(self) -> RunManifestArtifact:
        if self.result is None:
            raise RuntimeError("Capture session has not been finalized")
        return self.result.manifest

    def _elapsed_ms(self) -> float:
        if self._start_clock is None:
            return 0.0
        return (time.perf_counter() - self._start_clock) * 1000

    def record_query(
        self,
        sql: str,
        params: Any = None,
        *,
        duration_ms: float = 0.0,
        connection_alias: str = "default",
        vendor: str = "postgresql",
        many: bool = False,
        succeeded: bool = True,
        exception: Exception | None = None,
        transaction_depth: int = 0,
        autocommit: bool | None = True,
        row_count: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        if len(self._pending) >= self.policy_payload.limits.max_query_count:
            self._limit_reached = True
            return
        origin = capture_origin(
            mode=self.policy_payload.origin_capture_mode,
            application_roots=self.policy_payload.application_roots,
            exclude_module_patterns=self.policy_payload.exclude_module_patterns,
            max_stack_depth=self.policy_payload.limits.max_stack_depth,
        )
        self._pending.append(
            _PendingExecution(
                sequence_number=len(self._pending) + 1,
                connection_alias=connection_alias,
                vendor=vendor,
                started_offset_ms=max(0.0, self._elapsed_ms() - duration_ms),
                duration_ms=max(0.0, duration_ms),
                sql=sql,
                params=params,
                many=many,
                succeeded=succeeded,
                exception=exception,
                origin=origin,
                transaction_depth=transaction_depth,
                autocommit=autocommit,
                row_count=row_count,
                context=context or {},
            )
        )

    def _attach_django_wrappers(self, stack: ExitStack) -> None:
        try:
            from django.db import connections
        except Exception:
            return
        try:
            aliases = tuple(connections)
        except Exception:
            return
        include = set(self.policy_payload.include_connection_aliases)
        for alias in aliases:
            if include and alias not in include:
                continue
            try:
                connection = connections[alias]
                stack.enter_context(connection.execute_wrapper(self._django_wrapper(alias, connection)))
            except Exception:
                continue

    def _django_wrapper(self, alias: str, connection: Any):
        session = self

        class Wrapper:
            def __call__(self, execute, sql, params, many, context):
                if len(session._pending) >= session.policy_payload.limits.max_query_count:
                    session._limit_reached = True
                    return execute(sql, params, many, context)
                started_offset = session._elapsed_ms()
                origin = capture_origin(
                    mode=session.policy_payload.origin_capture_mode,
                    application_roots=session.policy_payload.application_roots,
                    exclude_module_patterns=session.policy_payload.exclude_module_patterns,
                    max_stack_depth=session.policy_payload.limits.max_stack_depth,
                )
                start = time.perf_counter()
                exception: Exception | None = None
                succeeded = True
                result = None
                try:
                    result = execute(sql, params, many, context)
                    return result
                except Exception as caught:
                    succeeded = False
                    exception = caught
                    raise
                finally:
                    duration = (time.perf_counter() - start) * 1000
                    cursor = context.get("cursor") if isinstance(context, dict) else None
                    row_count = getattr(cursor, "rowcount", None)
                    session._pending.append(
                        _PendingExecution(
                            sequence_number=len(session._pending) + 1,
                            connection_alias=alias,
                            vendor=getattr(connection, "vendor", "unknown"),
                            started_offset_ms=started_offset,
                            duration_ms=duration,
                            sql=str(sql),
                            params=params,
                            many=bool(many),
                            succeeded=succeeded,
                            exception=exception,
                            origin=origin,
                            transaction_depth=len(getattr(connection, "savepoint_ids", ())),
                            autocommit=getattr(connection, "autocommit", None),
                            row_count=row_count if isinstance(row_count, int) else None,
                            context={"django": True},
                        )
                    )

        return Wrapper()

    def _materialize_executions(self) -> tuple[QueryExecutionArtifact, ...]:
        artifacts: list[QueryExecutionArtifact] = []
        for pending in self._pending:
            policy = self.policy_payload
            if policy.raw_sql_mode == RawSqlMode.OMIT:
                sql = None
            elif policy.raw_sql_mode == RawSqlMode.REDACT:
                sql = redact_sql(pending.sql or "")
            else:
                sql = pending.sql
            if sql is not None:
                encoded = sql.encode("utf-8")
                if len(encoded) > policy.limits.max_raw_sql_bytes:
                    sql = encoded[: policy.limits.max_raw_sql_bytes].decode("utf-8", errors="ignore")
            parameters = capture_parameters(
                pending.params,
                mode=policy.parameter_capture_mode,
                hmac_key=self.hmac_key,
            )
            artifact = QueryExecutionArtifact(
                producer=self.producer,
                provenance=Provenance(code_revision=self.code_revision, derivation_key="query-capture.v1"),
                payload=QueryExecutionPayload(
                    run_id=self.run_id,
                    sequence_number=pending.sequence_number,
                    connection=QueryConnection(
                        alias=pending.connection_alias,
                        vendor=pending.vendor,
                    ),
                    timing=QueryTiming(
                        started_offset_ms=pending.started_offset_ms,
                        duration_ms=pending.duration_ms,
                    ),
                    raw_sql_mode=policy.raw_sql_mode,
                    sql=sql,
                    parameters=parameters,
                    parameter_binding_fingerprint=binding_fingerprint(parameters),
                    origin=pending.origin,
                    transaction=QueryTransaction(
                        transaction_id=(
                            f"{self.run_id}:txn:{pending.transaction_depth}"
                            if pending.transaction_depth
                            else None
                        ),
                        depth=pending.transaction_depth,
                        autocommit=pending.autocommit,
                    ),
                    outcome=QueryOutcome(
                        status="succeeded" if pending.succeeded else "failed",
                        row_count=pending.row_count,
                        exception_type=(type(pending.exception).__name__ if pending.exception else None),
                        exception_message=(str(pending.exception) if pending.exception else None),
                    ),
                    many=pending.many,
                    context=pending.context,
                ),
            )
            artifacts.append(artifact.seal())
        return tuple(artifacts)

    def _environment(self) -> EnvironmentProfileArtifact:
        components = [RuntimeComponent(name="planguard", version="0.5.0")]
        try:
            import django

            components.append(RuntimeComponent(name="django", version=django.get_version()))
        except Exception:
            components.append(
                RuntimeComponent(name="django", version=None, details={"available": False})
            )
        aliases = tuple(sorted({item.connection_alias for item in self._pending}))
        vendors = sorted({item.vendor for item in self._pending})
        return EnvironmentProfileArtifact(
            producer=self.producer,
            provenance=Provenance(code_revision=self.code_revision),
            payload=EnvironmentProfilePayload(
                operating_system=platform.system(),
                architecture=platform.machine(),
                python_version=platform.python_version(),
                runtime_components=tuple(components),
                database=DatabaseIdentity(
                    vendor=vendors[0] if len(vendors) == 1 else ("mixed" if vendors else "unknown"),
                    connection_aliases=aliases,
                ),
                environment_variables={"PLANGUARD_MODE": "capture"},
                machine_profile={"processor": platform.processor()},
            ),
        ).seal()

    def _finalize(self, operation_error: BaseException | None) -> CapturedRun:
        environment = self._environment()
        capture_policy = CapturePolicyArtifact(
            producer=self.producer,
            provenance=Provenance(code_revision=self.code_revision),
            payload=self.policy_payload,
        ).seal()
        executions = self._materialize_executions()
        analysis = AnalysisEngine(producer=self.producer).analyze(executions, run_id=self.run_id)
        policy_artifact: BudgetPolicyArtifact | None = None
        if isinstance(self.budget_policy, QueryPolicy):
            policy_artifact = BudgetPolicyArtifact(
                producer=self.producer,
                payload=self.budget_policy.to_payload(),
            ).seal()
        elif isinstance(self.budget_policy, BudgetPolicyArtifact):
            policy_artifact = self.budget_policy.seal()
        if policy_artifact is not None:
            evaluation = evaluate_policy(analysis, policy_artifact, producer=self.producer)
            analysis = AnalysisBundle(
                run_id=analysis.run_id,
                executions=analysis.executions,
                templates=analysis.templates,
                schemes=analysis.schemes,
                families=analysis.families,
                evidence=analysis.evidence,
                findings=analysis.findings,
                detector_receipts=analysis.detector_receipts,
                budget_evaluations=(evaluation,),
                workload_graphs=analysis.workload_graphs,
                workload_motifs=analysis.workload_motifs,
                workload_episodes=analysis.workload_episodes,
                plan_observations=analysis.plan_observations,
                plan_collection_receipts=analysis.plan_collection_receipts,
                summary=analysis.summary.model_copy(
                    update={
                        "payload": analysis.summary.payload.model_copy(
                            update={"budget_evaluation_refs": (evaluation.reference(),)}
                        )
                    }
                ).seal(),
            )

        saved = [environment, capture_policy]
        if policy_artifact is not None:
            saved.append(policy_artifact)
        saved.extend([*executions, *analysis.all_derived_artifacts()])
        for artifact in saved:
            self.store.save(artifact)
        counts: dict[str, int] = {}
        for artifact in saved:
            counts[artifact.artifact_kind] = counts.get(artifact.artifact_kind, 0) + 1
        status = RunStatus.FAILED if operation_error else RunStatus.COMPLETED
        manifest = RunManifestArtifact(
            artifact_id=self.run_id,
            producer=self.producer,
            provenance=Provenance(
                input_refs=tuple(item.reference() for item in saved),
                configuration_ref=capture_policy.reference(),
                code_revision=self.code_revision,
                derivation_key="capture-run-finalize.v1",
                notes=((f"Operation failed: {operation_error}",) if operation_error else ()),
            ),
            payload=RunManifestPayload(
                run=RunSummary(
                    name=self.name,
                    mode=self.mode,
                    started_at=self._started_at,
                    completed_at=self._completed_at,
                    status=status,
                    tags=self.tags,
                ),
                environment_ref=environment.reference(),
                capture_policy_ref=capture_policy.reference(),
                scenario_instance_ref=self.scenario_instance_ref,
                artifact_inventory=ArtifactInventory(
                    by_kind=dict(sorted(counts.items())),
                    total_count=sum(counts.values()),
                ),
                capability_status={
                    "query.capture.django": CapabilityStatus(
                        state=CapabilityState.SUPPORTED,
                        reason="Django execution-wrapper adapter is available when Django is installed.",
                    ),
                    "query.normalization": CapabilityStatus(
                        state=CapabilityState.PARTIAL,
                        reason="Milestone B uses a conservative parser with explicit fallback quality.",
                    ),
                    "query.family": CapabilityStatus(
                        state=CapabilityState.SUPPORTED,
                        reason="Four built-in family schemes were projected from observations.",
                    ),
                    "analysis.detectors": CapabilityStatus(
                        state=CapabilityState.SUPPORTED,
                        reason="Evidence-backed Milestone B detector suite executed.",
                    ),
                    "capture.limit_reached": CapabilityStatus(
                        state=CapabilityState.PARTIAL if self._limit_reached else CapabilityState.SUPPORTED,
                        reason=(
                            "Query count limit was reached; later queries were not captured."
                            if self._limit_reached
                            else "Capture completed within configured limits."
                        ),
                    ),
                },
                integrity=BundleIntegrity(verified=False),
            ),
        ).seal()
        self.store.save(manifest)
        return CapturedRun(
            manifest=manifest,
            environment=environment,
            capture_policy=capture_policy,
            analysis=analysis,
        )


def profile(name: str, **kwargs: Any) -> AnalysisSession:
    return AnalysisSession(name, **kwargs)


def current_session() -> AnalysisSession | None:
    return _ACTIVE_SESSION.get()
