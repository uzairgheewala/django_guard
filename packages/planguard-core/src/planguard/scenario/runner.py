"""Receipt-bearing generic scenario execution runner."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from planguard.artifacts.models import (
    ArtifactReference,
    DatasetManifestArtifact,
    OracleEvaluation,
    OracleStatus,
    ProducerIdentity,
    Provenance,
    ScenarioBindingArtifact,
    ScenarioInstanceArtifact,
    ScenarioPhaseReceiptArtifact,
    ScenarioPhaseReceiptPayload,
    ScenarioReceiptStatus,
    ScenarioRunArtifact,
    ScenarioRunPayload,
    ScenarioTemplateArtifact,
)
from planguard.canonical import canonical_json_bytes
from planguard.capture.session import AnalysisSession, CapturedRun
from planguard.ids import new_artifact_id
from planguard.scenario.registry import ScenarioRegistry
from planguard.store.filesystem import FilesystemArtifactStore
from planguard.time import utc_now


@dataclass(slots=True)
class ScenarioExecutionContext:
    scenario_run_id: str
    template: ScenarioTemplateArtifact
    binding: ScenarioBindingArtifact
    instance: ScenarioInstanceArtifact
    producer: ProducerIdentity
    store: FilesystemArtifactStore
    environment: dict[str, Any] = field(default_factory=dict)
    dataset: Any = None
    dataset_manifest: DatasetManifestArtifact | None = None
    mutation_state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OperationResult:
    value: Any
    state: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def result_digest(self) -> str:
        return "sha256:" + hashlib.sha256(canonical_json_bytes(self.value)).hexdigest()

    @property
    def state_digest(self) -> str | None:
        if self.state is None:
            return None
        return "sha256:" + hashlib.sha256(canonical_json_bytes(self.state)).hexdigest()


@dataclass(frozen=True, slots=True)
class ScenarioExecutionResult:
    scenario_run: ScenarioRunArtifact
    receipts: tuple[ScenarioPhaseReceiptArtifact, ...]
    captured_run: CapturedRun | None
    dataset_manifest: DatasetManifestArtifact | None


class ScenarioRunner:
    PHASES = (
        "prepare_environment",
        "prepare_dataset",
        "apply_mutations",
        "execute_operation",
        "evaluate_oracles",
        "cleanup",
    )

    def __init__(
        self,
        *,
        registry: ScenarioRegistry,
        store: FilesystemArtifactStore,
        producer: ProducerIdentity | None = None,
    ) -> None:
        self.registry = registry
        self.store = store
        self.producer = producer or ProducerIdentity(name="planguard", version="0.4.0", build="milestone-d")

    def _receipt(
        self,
        *,
        context: ScenarioExecutionContext,
        phase: str,
        status: ScenarioReceiptStatus,
        started: datetime,
        outputs: tuple[ArtifactReference, ...] = (),
        error: str | None = None,
        statistics: dict[str, Any] | None = None,
        gaps: tuple[str, ...] = (),
    ) -> ScenarioPhaseReceiptArtifact:
        item = ScenarioPhaseReceiptArtifact(
            producer=self.producer,
            provenance=Provenance(
                input_refs=(context.instance.reference(),),
                derivation_key=f"scenario-phase:{phase}.v1",
            ),
            payload=ScenarioPhaseReceiptPayload(
                scenario_instance_ref=context.instance.reference(),
                scenario_run_id=context.scenario_run_id,
                phase_key=phase,
                status=status,
                started_at=started,
                completed_at=utc_now(),
                output_refs=outputs,
                capability_gaps=gaps,
                error=error,
                statistics=statistics or {},
            ),
        ).seal()
        self.store.save(item)
        return item

    def run(self, instance: ScenarioInstanceArtifact) -> ScenarioExecutionResult:
        template = self.registry.template_for_ref(instance.payload.template_ref.artifact_id)
        binding = self.registry.binding_for_ref(instance.payload.binding_ref.artifact_id)
        adapter = self.registry.require_adapter(binding.payload.adapter_key)
        scenario_run_id = new_artifact_id("scrun")
        context = ScenarioExecutionContext(
            scenario_run_id=scenario_run_id,
            template=template,
            binding=binding,
            instance=instance,
            producer=self.producer,
            store=self.store,
        )
        self.store.save(instance)
        started_at = utc_now()
        receipts: list[ScenarioPhaseReceiptArtifact] = []
        captured: CapturedRun | None = None
        operation_result: OperationResult | None = None
        evaluations: list[OracleEvaluation] = []
        status = ScenarioReceiptStatus.SUCCEEDED
        error: Exception | None = None

        phase_started = utc_now()
        try:
            context.environment = adapter.prepare_environment(context) or {}
            receipts.append(self._receipt(context=context, phase="prepare_environment", status=ScenarioReceiptStatus.SUCCEEDED, started=phase_started, statistics=context.environment))

            phase_started = utc_now()
            built = adapter.prepare_dataset(context)
            if isinstance(built, tuple) and len(built) == 2:
                context.dataset, context.dataset_manifest = built
            else:
                context.dataset = built
            output_refs: tuple[ArtifactReference, ...] = ()
            if context.dataset_manifest is not None:
                self.store.save(context.dataset_manifest)
                output_refs = (context.dataset_manifest.reference(),)
            receipts.append(self._receipt(context=context, phase="prepare_dataset", status=ScenarioReceiptStatus.SUCCEEDED, started=phase_started, outputs=output_refs, statistics={"dataset_type": type(context.dataset).__name__}))

            phase_started = utc_now()
            applied = []
            for item in sorted(instance.payload.applied_mutations, key=lambda value: value.order):
                mutation = self.registry.mutation_for_ref(item.mutation_ref.artifact_id)
                adapter.apply_mutation(context, mutation, dict(item.parameter_bindings))
                applied.append(mutation.payload.mutation_key)
            receipts.append(self._receipt(context=context, phase="apply_mutations", status=ScenarioReceiptStatus.SUCCEEDED, started=phase_started, statistics={"applied_mutations": applied}))

            phase_started = utc_now()
            analysis_run_id = new_artifact_id("run")
            with AnalysisSession(
                f"Scenario: {template.payload.title}",
                store=self.store,
                mode="laboratory",
                tags=("scenario", template.payload.template_key, binding.payload.binding_key, *instance.payload.tags),
                producer=self.producer,
                attach_django=False,
                run_id=analysis_run_id,
                code_revision="milestone-d",
                scenario_instance_ref=instance.reference(),
            ) as session:
                raw_result = adapter.execute(context, session)
                operation_result = raw_result if isinstance(raw_result, OperationResult) else OperationResult(value=raw_result)
            captured = session.result
            outputs = (captured.manifest.reference(),) if captured else ()
            receipts.append(self._receipt(context=context, phase="execute_operation", status=ScenarioReceiptStatus.SUCCEEDED, started=phase_started, outputs=outputs, statistics={"query_count": captured.analysis.summary.payload.query_count if captured else 0}))

            phase_started = utc_now()
            if operation_result is None:
                raise RuntimeError("Scenario adapter did not produce an operation result")
            for oracle in template.payload.oracles:
                evaluated = adapter.evaluate_oracle(context, oracle, operation_result)
                if isinstance(evaluated, OracleEvaluation):
                    evaluations.append(evaluated)
                elif evaluated is None:
                    evaluations.append(OracleEvaluation(oracle_key=oracle.oracle_key, status=OracleStatus.NOT_EVALUATED, explanation="Adapter did not evaluate this oracle."))
                else:
                    evaluations.append(OracleEvaluation(oracle_key=oracle.oracle_key, status=OracleStatus.SATISFIED if bool(evaluated) else OracleStatus.NOT_SATISFIED, measured_value=evaluated, expected_value=True, explanation="Adapter returned a boolean-compatible oracle result."))
            failed_required = [item for item in evaluations if item.status == OracleStatus.NOT_SATISFIED and next((o.disposition for o in template.payload.oracles if o.oracle_key == item.oracle_key), "fail") == "fail"]
            if failed_required:
                status = ScenarioReceiptStatus.FAILED
            receipts.append(self._receipt(context=context, phase="evaluate_oracles", status=ScenarioReceiptStatus.SUCCEEDED if not failed_required else ScenarioReceiptStatus.FAILED, started=phase_started, statistics={"evaluated": len(evaluations), "failed": len(failed_required)}))
        except Exception as exc:
            error = exc
            status = ScenarioReceiptStatus.FAILED
            receipts.append(self._receipt(context=context, phase=self.PHASES[min(len(receipts), len(self.PHASES)-1)], status=ScenarioReceiptStatus.FAILED, started=phase_started, error=f"{type(exc).__name__}: {exc}"))
        finally:
            phase_started = utc_now()
            try:
                cleanup_statistics = adapter.cleanup(context) or {}
                receipts.append(self._receipt(context=context, phase="cleanup", status=ScenarioReceiptStatus.SUCCEEDED, started=phase_started, statistics=cleanup_statistics))
            except Exception as cleanup_error:
                status = ScenarioReceiptStatus.FAILED
                receipts.append(self._receipt(context=context, phase="cleanup", status=ScenarioReceiptStatus.FAILED, started=phase_started, error=f"{type(cleanup_error).__name__}: {cleanup_error}"))

        completed_at = utc_now()
        scenario_run = ScenarioRunArtifact(
            artifact_id=scenario_run_id,
            producer=self.producer,
            provenance=Provenance(
                input_refs=(instance.reference(), *(item.reference() for item in receipts), *((context.dataset_manifest.reference(),) if context.dataset_manifest else ()), *((captured.manifest.reference(),) if captured else ())),
                configuration_ref=binding.reference(),
                derivation_key="scenario-run.v1",
                notes=((f"Execution failed: {error}",) if error else ()),
            ),
            payload=ScenarioRunPayload(
                scenario_run_id=scenario_run_id,
                scenario_instance_ref=instance.reference(),
                dataset_ref=context.dataset_manifest.reference() if context.dataset_manifest else None,
                analysis_run_ref=captured.manifest.reference() if captured else None,
                status=status,
                variant_key=instance.payload.variant_key,
                phase_receipt_refs=tuple(item.reference() for item in receipts),
                oracle_evaluations=tuple(evaluations),
                result_digest=operation_result.result_digest if operation_result else None,
                state_digest=operation_result.state_digest if operation_result else None,
                started_at=started_at,
                completed_at=completed_at,
                metadata={"template_key": template.payload.template_key, "binding_key": binding.payload.binding_key, **(operation_result.metadata if operation_result else {})},
            ),
        ).seal()
        self.store.save(scenario_run)
        return ScenarioExecutionResult(scenario_run=scenario_run, receipts=tuple(receipts), captured_run=captured, dataset_manifest=context.dataset_manifest)
