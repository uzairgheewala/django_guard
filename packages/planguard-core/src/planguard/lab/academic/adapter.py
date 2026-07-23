"""Academic implementation of the generic scenario adapter contract."""

from __future__ import annotations

import math
from typing import Any, Callable

from planguard.artifacts.models import MutationDefinitionArtifact, OracleDefinition, OracleEvaluation, OracleStatus
from planguard.capture.session import AnalysisSession
from planguard.lab.academic.generator import AcademicDatasetGenerator
from planguard.lab.academic.models import AcademicDataset
from planguard.scenario.runner import OperationResult, ScenarioExecutionContext


class AcademicScenarioAdapter:
    adapter_key = "academic-lab.v1"

    def prepare_environment(self, context: ScenarioExecutionContext) -> dict[str, Any]:
        return {
            "application": "academic-lab.v1",
            "database_semantics": "postgresql-simulated",
            "query_capture": "manual-deterministic",
            "variant": context.instance.payload.variant_key,
        }

    def prepare_dataset(self, context: ScenarioExecutionContext):
        params = context.instance.payload.parameter_bindings
        generator = AcademicDatasetGenerator(context.producer)
        return generator.generate(
            seed=context.instance.payload.seed,
            scale_profile=str(params.get("scale_profile", "tiny")),
            tenant_skew=str(params.get("tenant_skew", "uniform")),
            relation_fanout=int(params.get("relation_fanout", 5)),
        )

    def apply_mutation(self, context: ScenarioExecutionContext, mutation: MutationDefinitionArtifact, parameters: dict[str, Any]) -> None:
        key = mutation.payload.mutation_key
        context.mutation_state[key] = parameters or True
        if key == "increase-tenant-skew.v1" and context.dataset is not None:
            context.dataset.tenant_skew = "dominant"
        if key == "increase-relation-fanout.v1":
            context.metadata["fanout_multiplier"] = float(parameters.get("multiplier", 2.0))
        if key == "extend-transaction-scope.v1":
            context.metadata["force_long_transaction"] = True

    def execute(self, context: ScenarioExecutionContext, session: AnalysisSession) -> OperationResult:
        operation = next(item.target for item in context.binding.payload.role_bindings if item.role_key == "operation")
        dispatch: dict[str, Callable[[ScenarioExecutionContext, AnalysisSession], OperationResult]] = {
            "academic.plan_items_with_courses": self._relation_fanout,
            "academic.students_enrollments_courses": self._nested_fanout,
            "academic.repeated_plan_evaluation": self._repeated_evaluation,
            "academic.advisor_roster": self._count_then_fetch,
            "academic.transcript_import": self._check_write,
            "academic.audit_status_update": self._per_item_update,
            "academic.graduation_risk_report": self._aggregate_report,
            "academic.course_search": self._offset_pagination,
            "academic.institution_dashboard": self._tenant_dashboard,
            "academic.catalog_update": self._long_transaction,
        }
        try:
            return dispatch[operation](context, session)
        except KeyError as exc:
            raise ValueError(f"Unsupported academic operation binding: {operation}") from exc

    def evaluate_oracle(self, context: ScenarioExecutionContext, oracle: OracleDefinition, result: OperationResult) -> OracleEvaluation:
        if oracle.kind == "result_nonempty":
            measured = bool(result.value)
            return OracleEvaluation(oracle_key=oracle.oracle_key, status=OracleStatus.SATISFIED if measured else OracleStatus.NOT_SATISFIED, measured_value=measured, expected_value=True, explanation="The operation produced a non-empty deterministic result." if measured else "The operation returned no result rows.")
        if oracle.kind == "tenant_isolation":
            isolated = bool(result.metadata.get("tenant_isolated", False))
            return OracleEvaluation(oracle_key=oracle.oracle_key, status=OracleStatus.SATISFIED if isolated else OracleStatus.NOT_SATISFIED, measured_value=isolated, expected_value=True, explanation="Every returned domain row belongs to the selected institution." if isolated else "At least one row crossed the selected institution boundary.")
        if oracle.kind == "variant_query_bound":
            actual = int(result.metadata.get("query_count", 0))
            parent_count = int(context.instance.payload.parameter_bindings.get("parent_count", 8))
            expected = max(3, parent_count // 2 + 3) if context.instance.payload.variant_key == "optimized" else max(1, parent_count * 4 + 10)
            satisfied = actual <= expected
            return OracleEvaluation(oracle_key=oracle.oracle_key, status=OracleStatus.SATISFIED if satisfied else OracleStatus.NOT_SATISFIED, measured_value=actual, expected_value={"maximum": expected}, explanation=f"Observed {actual} queries against a variant-aware bound of {expected}.")
        return OracleEvaluation(oracle_key=oracle.oracle_key, status=OracleStatus.NOT_EVALUATED, explanation=f"Academic adapter does not implement oracle kind {oracle.kind!r}.")

    def cleanup(self, context: ScenarioExecutionContext) -> dict[str, Any]:
        return {"dataset_released": True, "mutation_count": len(context.mutation_state)}

    @staticmethod
    def _txn(context: ScenarioExecutionContext) -> tuple[int, bool]:
        scope = str(context.instance.payload.parameter_bindings.get("transaction_scope", "autocommit"))
        if context.metadata.get("force_long_transaction") or scope == "long_atomic":
            return 1, False
        if scope == "short_atomic":
            return 1, False
        return 0, True

    @staticmethod
    def _duration(base: float, *, context: ScenarioExecutionContext, amplification: float = 1.0) -> float:
        scale = {"tiny": 1.0, "small": 1.4, "medium": 2.2, "large": 3.8}[context.dataset.scale_profile]
        skew = 1.8 if context.dataset.tenant_skew == "dominant" else (1.3 if context.dataset.tenant_skew == "zipf" else 1.0)
        index = 2.5 if "remove-composite-tenant-index.v1" in context.mutation_state else 1.0
        stale = 1.4 if "stale-statistics.v1" in context.mutation_state else 1.0
        hydration = 1.7 if "expand-object-hydration.v1" in context.mutation_state else 1.0
        return round(base * scale * skew * index * stale * hydration * amplification, 3)

    @staticmethod
    def _target_student(dataset: AcademicDataset):
        return dataset.students[0]

    def _relation_fanout(self, context: ScenarioExecutionContext, session: AnalysisSession) -> OperationResult:
        dataset = context.dataset
        student = self._target_student(dataset)
        items = dataset.plan_items_for_student(student.id)
        requested = int(context.instance.payload.parameter_bindings.get("parent_count", len(items)))
        items = items[: min(requested, len(items))]
        txn, autocommit = self._txn(context)
        session.record_query("SELECT id, course_id FROM plan_item WHERE institution_id = %s AND student_id = %s ORDER BY position LIMIT %s", [student.institution_id, student.id, requested], duration_ms=self._duration(3.2, context=context), row_count=len(items), transaction_depth=txn, autocommit=autocommit, context={"operation_segment": "load-parents"})
        rows = []
        naive = context.instance.payload.variant_key == "naive" or "remove-eager-loading.v1" in context.mutation_state
        if naive:
            for item in items:
                course = dataset.course(item.course_id)
                session.record_query("SELECT id, subject, number, title FROM course WHERE institution_id = %s AND id = %s", [student.institution_id, course.id], duration_ms=self._duration(0.9, context=context), row_count=1, transaction_depth=txn, autocommit=autocommit, context={"operation_segment": "load-related", "relation": "course"})
                rows.append({"plan_item_id": item.id, "course": f"{course.subject}{course.number}", "institution_id": course.institution_id})
        else:
            ids = [item.course_id for item in items]
            session.record_query("SELECT id, subject, number, title FROM course WHERE institution_id = %s AND id = ANY(%s)", [student.institution_id, ids], duration_ms=self._duration(1.8, context=context, amplification=max(1.0, len(ids) / 20)), row_count=len(ids), transaction_depth=txn, autocommit=autocommit, context={"operation_segment": "batch-load-related", "relation": "course"})
            courses = {item.id: item for item in dataset.courses if item.id in ids}
            rows = [{"plan_item_id": item.id, "course": f"{courses[item.course_id].subject}{courses[item.course_id].number}", "institution_id": courses[item.course_id].institution_id} for item in items]
        return self._result(rows, student.institution_id, session)

    def _nested_fanout(self, context: ScenarioExecutionContext, session: AnalysisSession) -> OperationResult:
        dataset = context.dataset
        tenant = dataset.institutions[0].id
        count = int(context.instance.payload.parameter_bindings.get("parent_count", 8))
        students = dataset.students_for_tenant(tenant)[:count]
        txn, autocommit = self._txn(context)
        session.record_query("SELECT id FROM student WHERE institution_id = %s AND active = TRUE LIMIT %s", [tenant, count], duration_ms=self._duration(4.0, context=context), row_count=len(students), transaction_depth=txn, autocommit=autocommit)
        output = []
        if context.instance.payload.variant_key == "naive":
            for student in students:
                enrollments = dataset.enrollments_for_student(student.id)
                session.record_query("SELECT id, course_id FROM enrollment WHERE institution_id = %s AND student_id = %s", [tenant, student.id], duration_ms=self._duration(1.1, context=context), row_count=len(enrollments), transaction_depth=txn, autocommit=autocommit)
                for enrollment in enrollments[:3]:
                    course = dataset.course(enrollment.course_id)
                    session.record_query("SELECT id, subject, number FROM course WHERE institution_id = %s AND id = %s", [tenant, course.id], duration_ms=self._duration(0.7, context=context), row_count=1, transaction_depth=txn, autocommit=autocommit)
                    output.append({"student_id": student.id, "course_id": course.id, "institution_id": tenant})
        else:
            ids = [item.id for item in students]
            enrollments = [item for item in dataset.enrollments if item.student_id in ids]
            session.record_query("SELECT student_id, course_id FROM enrollment WHERE institution_id = %s AND student_id = ANY(%s)", [tenant, ids], duration_ms=self._duration(2.5, context=context), row_count=len(enrollments), transaction_depth=txn, autocommit=autocommit)
            course_ids = sorted({item.course_id for item in enrollments})
            session.record_query("SELECT id, subject, number FROM course WHERE institution_id = %s AND id = ANY(%s)", [tenant, course_ids], duration_ms=self._duration(2.1, context=context), row_count=len(course_ids), transaction_depth=txn, autocommit=autocommit)
            output = [{"student_id": item.student_id, "course_id": item.course_id, "institution_id": tenant} for item in enrollments[: count * 3]]
        return self._result(output, tenant, session)

    def _repeated_evaluation(self, context: ScenarioExecutionContext, session: AnalysisSession) -> OperationResult:
        student = self._target_student(context.dataset)
        items = context.dataset.plan_items_for_student(student.id)
        repeats = 4 if context.instance.payload.variant_key == "naive" else 1
        for phase in range(repeats):
            session.record_query("SELECT id, course_id, position FROM plan_item WHERE institution_id = %s AND student_id = %s ORDER BY position", [student.institution_id, student.id], duration_ms=self._duration(1.8, context=context), row_count=len(items), context={"evaluation_phase": phase})
        rows = [{"id": item.id, "institution_id": item.institution_id} for item in items]
        return self._result(rows, student.institution_id, session)

    def _count_then_fetch(self, context: ScenarioExecutionContext, session: AnalysisSession) -> OperationResult:
        tenant = context.dataset.institutions[0].id
        students = context.dataset.students_for_tenant(tenant)
        if context.instance.payload.variant_key == "naive":
            session.record_query("SELECT COUNT(*) FROM student WHERE institution_id = %s AND active = TRUE", [tenant], duration_ms=self._duration(2.0, context=context), row_count=1)
        session.record_query("SELECT id, external_id FROM student WHERE institution_id = %s AND active = TRUE ORDER BY id LIMIT %s", [tenant, 50], duration_ms=self._duration(3.0, context=context), row_count=min(50, len(students)))
        return self._result([{"student_id": item.id, "institution_id": tenant} for item in students[:50]], tenant, session)

    def _check_write(self, context: ScenarioExecutionContext, session: AnalysisSession) -> OperationResult:
        student = self._target_student(context.dataset)
        batch = min(int(context.instance.payload.parameter_bindings.get("batch_size", 10)), 25)
        rows = []
        force = "force-per-row-write.v1" in context.mutation_state
        if context.instance.payload.variant_key == "naive" or force:
            for index in range(batch):
                session.record_query("SELECT 1 FROM enrollment WHERE institution_id = %s AND student_id = %s AND source_key = %s", [student.institution_id, student.id, f"SRC-{index}"], duration_ms=self._duration(0.7, context=context), row_count=0)
                session.record_query("INSERT INTO enrollment (institution_id, student_id, course_id, source_key) VALUES (%s, %s, %s, %s)", [student.institution_id, student.id, context.dataset.courses[index % len(context.dataset.courses)].id, f"SRC-{index}"], duration_ms=self._duration(1.0, context=context), row_count=1)
                rows.append({"source_key": f"SRC-{index}", "institution_id": student.institution_id})
        else:
            keys = [f"SRC-{index}" for index in range(batch)]
            session.record_query("SELECT source_key FROM enrollment WHERE institution_id = %s AND student_id = %s AND source_key = ANY(%s)", [student.institution_id, student.id, keys], duration_ms=self._duration(1.4, context=context), row_count=0)
            session.record_query("INSERT INTO enrollment (...) VALUES (...) ON CONFLICT DO NOTHING", [batch], duration_ms=self._duration(2.0, context=context), row_count=batch, many=True)
            rows = [{"source_key": key, "institution_id": student.institution_id} for key in keys]
        return self._result(rows, student.institution_id, session, state={"inserted": len(rows)})

    def _per_item_update(self, context: ScenarioExecutionContext, session: AnalysisSession) -> OperationResult:
        tenant = context.dataset.institutions[0].id
        students = context.dataset.students_for_tenant(tenant)[: min(25, int(context.instance.payload.parameter_bindings.get("parent_count", 8)))]
        force = "force-per-row-write.v1" in context.mutation_state
        if context.instance.payload.variant_key == "naive" or force:
            for student in students:
                session.record_query("UPDATE audit_summary SET risk_score = %s WHERE institution_id = %s AND student_id = %s", [student.id % 10, tenant, student.id], duration_ms=self._duration(0.9, context=context), row_count=1)
        else:
            session.record_query("UPDATE audit_summary SET risk_score = payload.score FROM (VALUES ...) payload(student_id, score) WHERE audit_summary.institution_id = %s AND audit_summary.student_id = payload.student_id", [tenant, len(students)], duration_ms=self._duration(2.1, context=context), row_count=len(students), many=True)
        return self._result([{"student_id": item.id, "institution_id": tenant} for item in students], tenant, session, state={"updated": len(students)})

    def _aggregate_report(self, context: ScenarioExecutionContext, session: AnalysisSession) -> OperationResult:
        tenant = context.dataset.institutions[0].id
        students = context.dataset.students_for_tenant(tenant)[: min(30, int(context.instance.payload.parameter_bindings.get("parent_count", 8)))]
        rows = []
        if context.instance.payload.variant_key == "naive":
            session.record_query("SELECT id FROM student WHERE institution_id = %s AND active = TRUE", [tenant], duration_ms=self._duration(3.0, context=context), row_count=len(students))
            for student in students:
                session.record_query("SELECT COUNT(*) FROM enrollment WHERE institution_id = %s AND student_id = %s", [tenant, student.id], duration_ms=self._duration(1.0, context=context), row_count=1)
                session.record_query("SELECT COUNT(*) FROM plan_item WHERE institution_id = %s AND student_id = %s", [tenant, student.id], duration_ms=self._duration(1.0, context=context), row_count=1)
                rows.append({"student_id": student.id, "institution_id": tenant, "risk": student.id % 5})
        else:
            session.record_query("SELECT s.id, COUNT(DISTINCT e.id), COUNT(DISTINCT p.id) FROM student s LEFT JOIN enrollment e ON (...) LEFT JOIN plan_item p ON (...) WHERE s.institution_id = %s GROUP BY s.id", [tenant], duration_ms=self._duration(6.0, context=context), row_count=len(students))
            rows = [{"student_id": student.id, "institution_id": tenant, "risk": student.id % 5} for student in students]
        return self._result(rows, tenant, session)

    def _offset_pagination(self, context: ScenarioExecutionContext, session: AnalysisSession) -> OperationResult:
        tenant = context.dataset.institutions[0].id
        offset = int(context.instance.payload.parameter_bindings.get("page_offset", 0))
        if context.instance.payload.variant_key == "naive":
            session.record_query("SELECT id, subject, number, title FROM course WHERE institution_id = %s ORDER BY subject, number LIMIT 20 OFFSET %s", [tenant, offset], duration_ms=self._duration(1.5 + math.log10(offset + 1), context=context), row_count=20)
        else:
            cursor = max(0, offset)
            session.record_query("SELECT id, subject, number, title FROM course WHERE institution_id = %s AND id > %s ORDER BY id LIMIT 20", [tenant, cursor], duration_ms=self._duration(1.4, context=context), row_count=20)
        courses = [item for item in context.dataset.courses if item.institution_id == tenant][:20]
        return self._result([{"course_id": item.id, "institution_id": tenant} for item in courses], tenant, session)

    def _tenant_dashboard(self, context: ScenarioExecutionContext, session: AnalysisSession) -> OperationResult:
        tenant = context.dataset.institutions[0].id
        logical = context.dataset.logical_counts["student"]
        session.record_query("SELECT status, COUNT(*) FROM student WHERE institution_id = %s GROUP BY status", [tenant], duration_ms=self._duration(3.0 + math.log10(logical + 1), context=context), row_count=4, context={"tenant_skew": context.dataset.tenant_skew, "logical_rows": logical})
        rows = [{"status": status, "count": logical // 4, "institution_id": tenant} for status in ("active", "risk", "inactive", "graduating")]
        return self._result(rows, tenant, session)

    def _long_transaction(self, context: ScenarioExecutionContext, session: AnalysisSession) -> OperationResult:
        tenant = context.dataset.institutions[0].id
        courses = [item for item in context.dataset.courses if item.institution_id == tenant][: min(20, int(context.instance.payload.parameter_bindings.get("parent_count", 8)))]
        long_scope = context.instance.payload.variant_key == "naive" or context.metadata.get("force_long_transaction")
        for index, course in enumerate(courses):
            depth = 1 if long_scope else (1 if index % 4 == 0 else 0)
            session.record_query("UPDATE course SET title = %s WHERE institution_id = %s AND id = %s", [course.title, tenant, course.id], duration_ms=self._duration(0.8, context=context), row_count=1, transaction_depth=depth, autocommit=not bool(depth))
        return self._result([{"course_id": item.id, "institution_id": tenant} for item in courses], tenant, session, state={"updated": len(courses)})

    @staticmethod
    def _result(rows: list[dict[str, Any]], tenant: int, session: AnalysisSession, *, state: Any = None) -> OperationResult:
        isolated = all(row.get("institution_id") == tenant for row in rows)
        return OperationResult(value=rows, state=state, metadata={"tenant_isolated": isolated, "query_count": len(session._pending), "result_count": len(rows)})
