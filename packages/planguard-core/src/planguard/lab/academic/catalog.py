"""Generic scenario templates and academic bindings for Milestone D."""

from __future__ import annotations

from planguard.artifacts.models import (
    CoverageObligation,
    MutationDefinitionArtifact,
    MutationDefinitionPayload,
    OracleDefinition,
    ParameterDomain,
    ParameterDomainKind,
    ProducerIdentity,
    Provenance,
    RoleBinding,
    ScenarioBindingArtifact,
    ScenarioBindingPayload,
    ScenarioOperationEdge,
    ScenarioOperationNode,
    ScenarioParameter,
    ScenarioRole,
    ScenarioRoleKind,
    ScenarioTemplateArtifact,
    ScenarioTemplatePayload,
    ScenarioVariant,
    VariantBinding,
)
from planguard.canonical import canonical_json_bytes
from planguard.ids import content_derived_id
from planguard.time import semantic_epoch


def _stable(prefix: str, payload, producer: ProducerIdentity) -> str:
    return content_derived_id(prefix, canonical_json_bytes({"payload": payload, "producer": producer.model_dump(mode="python")}), length=32)


def _common_parameters() -> tuple[ScenarioParameter, ...]:
    return (
        ScenarioParameter(parameter_key="scale_profile", domain=ParameterDomain(kind=ParameterDomainKind.FINITE, values=("tiny", "small", "medium", "large"), default="tiny"), required=False),
        ScenarioParameter(parameter_key="tenant_skew", domain=ParameterDomain(kind=ParameterDomainKind.FINITE, values=("uniform", "dominant", "zipf"), default="uniform"), required=False),
        ScenarioParameter(parameter_key="parent_count", domain=ParameterDomain(kind=ParameterDomainKind.INTEGER_RANGE, minimum=0, maximum=1000, default=8), required=False),
        ScenarioParameter(parameter_key="relation_fanout", domain=ParameterDomain(kind=ParameterDomainKind.INTEGER_RANGE, minimum=0, maximum=100, default=5), required=False),
        ScenarioParameter(parameter_key="batch_size", domain=ParameterDomain(kind=ParameterDomainKind.INTEGER_RANGE, minimum=1, maximum=1000, default=50), required=False),
        ScenarioParameter(parameter_key="page_offset", domain=ParameterDomain(kind=ParameterDomainKind.INTEGER_RANGE, minimum=0, maximum=1000000, default=0), required=False),
        ScenarioParameter(parameter_key="transaction_scope", domain=ParameterDomain(kind=ParameterDomainKind.FINITE, values=("autocommit", "short_atomic", "long_atomic"), default="autocommit"), required=False),
    )


def _template(producer: ProducerIdentity, *, key: str, title: str, description: str, operation_kind: str, mechanism: str) -> ScenarioTemplateArtifact:
    payload = ScenarioTemplatePayload(
        template_key=key,
        title=title,
        description=description,
        roles=(
            ScenarioRole(role_key="primary_entity", kind=ScenarioRoleKind.RELATIONAL_ENTITY),
            ScenarioRole(role_key="related_entity", kind=ScenarioRoleKind.RELATIONAL_ENTITY, required=False),
            ScenarioRole(role_key="operation", kind=ScenarioRoleKind.APPLICATION_OPERATION),
            ScenarioRole(role_key="dataset", kind=ScenarioRoleKind.DATASET),
            ScenarioRole(role_key="result", kind=ScenarioRoleKind.RESULT),
        ),
        parameters=_common_parameters(),
        operation_nodes=(
            ScenarioOperationNode(node_key="prepare", kind="prepare_dataset", role_ref="dataset", phase="prepare_dataset"),
            ScenarioOperationNode(node_key="execute", kind=operation_kind, role_ref="operation", phase="execute_operation"),
            ScenarioOperationNode(node_key="result", kind="result", role_ref="result", phase="evaluate_oracles"),
        ),
        operation_edges=(
            ScenarioOperationEdge(from_node="prepare", to_node="execute", kind="control_flow"),
            ScenarioOperationEdge(from_node="execute", to_node="result", kind="produces"),
        ),
        variants=(
            ScenarioVariant(variant_key="naive", title="Naive", implementation_role="operation.naive", tags=("baseline",)),
            ScenarioVariant(variant_key="optimized", title="Optimized", implementation_role="operation.optimized", tags=("candidate",)),
        ),
        oracles=(
            OracleDefinition(oracle_key="result-nonempty", kind="result_nonempty", disposition="fail"),
            OracleDefinition(oracle_key="tenant-isolation", kind="tenant_isolation", disposition="fail"),
            OracleDefinition(oracle_key="query-bound", kind="variant_query_bound", parameters={"mechanism": mechanism}, disposition="warn"),
        ),
        coverage_obligations=(
            CoverageObligation(obligation_key="scale-boundaries", kind="boundary_partitions", parameters={"parameter": "parent_count"}),
            CoverageObligation(obligation_key="scale-skew-pairwise", kind="pairwise", parameters={"parameters": ["scale_profile", "tenant_skew"]}),
            CoverageObligation(obligation_key=f"mechanism:{mechanism}", kind="mechanism", parameters={"mechanism": mechanism}),
        ),
        tags=("generic", "database-workload", mechanism),
    )
    return ScenarioTemplateArtifact(created_at=semantic_epoch(), artifact_id=_stable("sct", payload, producer), producer=producer, provenance=Provenance(derivation_key="builtin-scenario-template.v1"), payload=payload).seal()


_TEMPLATE_SPECS = (
    ("relation-access-fanout.v1", "Relation access fan-out", "Iterate parent rows and access one related entity per parent.", "relation_access", "round-trip-amplification"),
    ("nested-relation-fanout.v1", "Nested relation fan-out", "Traverse two related collection levels from each root entity.", "nested_relation_access", "nested-round-trip-amplification"),
    ("repeated-evaluation.v1", "Repeated evaluation", "Evaluate one logical collection repeatedly within an operation.", "repeated_evaluation", "redundant-execution"),
    ("count-then-fetch.v1", "Count then fetch", "Count and subsequently retrieve an equivalent collection.", "count_then_fetch", "duplicate-work"),
    ("per-item-check-write.v1", "Per-item check and write", "Perform an existence check followed by a write for each input item.", "check_write", "write-amplification"),
    ("per-item-update.v1", "Per-item update", "Update records individually rather than through one bounded bulk operation.", "per_item_update", "write-amplification"),
    ("aggregate-report.v1", "Aggregate report amplification", "Compute a report by issuing repeated subqueries for each subject.", "aggregate_report", "report-amplification"),
    ("offset-pagination.v1", "Offset pagination degradation", "Retrieve a deep page through offset-based pagination.", "offset_pagination", "pagination-amplification"),
    ("tenant-skew-sensitivity.v1", "Tenant skew sensitivity", "Execute a tenant-scoped query under uniform and dominant-tenant distributions.", "tenant_scoped", "data-skew-sensitivity"),
    ("long-transaction-accumulation.v1", "Long transaction accumulation", "Accumulate otherwise modest operations inside one broad transaction.", "long_transaction", "excessive-transaction-scope"),
)


def builtin_templates(producer: ProducerIdentity) -> tuple[ScenarioTemplateArtifact, ...]:
    return tuple(_template(producer, key=key, title=title, description=description, operation_kind=operation, mechanism=mechanism) for key, title, description, operation, mechanism in _TEMPLATE_SPECS)


_BINDING_SPECS = {
    "relation-access-fanout.v1": ("academic.plan-item-course.v1", "PlanItem", "Course", "academic.plan_items_with_courses"),
    "nested-relation-fanout.v1": ("academic.student-enrollment-offering.v1", "Student", "Enrollment", "academic.students_enrollments_courses"),
    "repeated-evaluation.v1": ("academic.student-plan-queryset.v1", "StudentPlan", "PlanItem", "academic.repeated_plan_evaluation"),
    "count-then-fetch.v1": ("academic.advisor-roster.v1", "AdvisorRoster", "Student", "academic.advisor_roster"),
    "per-item-check-write.v1": ("academic.transcript-import.v1", "TransferRecord", "Enrollment", "academic.transcript_import"),
    "per-item-update.v1": ("academic.audit-status-recalculation.v1", "Student", "AuditSummary", "academic.audit_status_update"),
    "aggregate-report.v1": ("academic.graduation-risk-report.v1", "Student", "AuditSummary", "academic.graduation_risk_report"),
    "offset-pagination.v1": ("academic.course-search.v1", "Course", "Course", "academic.course_search"),
    "tenant-skew-sensitivity.v1": ("academic.institution-dashboard.v1", "Institution", "Student", "academic.institution_dashboard"),
    "long-transaction-accumulation.v1": ("academic.catalog-update.v1", "Course", "Course", "academic.catalog_update"),
}


def builtin_bindings(producer: ProducerIdentity, templates: tuple[ScenarioTemplateArtifact, ...]) -> tuple[ScenarioBindingArtifact, ...]:
    output = []
    by_key = {item.payload.template_key: item for item in templates}
    for template_key, (binding_key, primary, related, operation) in _BINDING_SPECS.items():
        template = by_key[template_key]
        payload = ScenarioBindingPayload(
            binding_key=binding_key,
            template_ref=template.reference(),
            application_key="academic-lab.v1",
            role_bindings=(
                RoleBinding(role_key="primary_entity", binding_kind="model", target=f"academic_lab.{primary}"),
                RoleBinding(role_key="related_entity", binding_kind="model", target=f"academic_lab.{related}"),
                RoleBinding(role_key="operation", binding_kind="callable", target=operation),
                RoleBinding(role_key="dataset", binding_kind="dataset", target="academic.synthetic.v1"),
                RoleBinding(role_key="result", binding_kind="value", target="academic.operation-result.v1"),
            ),
            variant_bindings=(
                VariantBinding(variant_key="naive", target=f"{operation}.naive"),
                VariantBinding(variant_key="optimized", target=f"{operation}.optimized"),
            ),
            adapter_key="academic-lab.v1",
            capabilities=("scenario.execution", "dataset.synthetic", "query.capture.manual"),
            tags=("academic", template_key),
        )
        output.append(ScenarioBindingArtifact(created_at=semantic_epoch(), artifact_id=_stable("scb", payload, producer), producer=producer, provenance=Provenance(input_refs=(template.reference(),), derivation_key="academic-scenario-binding.v1"), payload=payload).seal())
    return tuple(output)


def builtin_mutations(producer: ProducerIdentity) -> tuple[MutationDefinitionArtifact, ...]:
    specs = (
        ("remove-eager-loading.v1", "Remove eager loading", "application", "Remove batching/eager relation loading from the active variant.", ("relation-access-fanout.v1", "nested-relation-fanout.v1")),
        ("force-per-row-write.v1", "Force per-row writes", "application", "Replace a bulk mutation with one statement per item.", ("per-item-check-write.v1", "per-item-update.v1")),
        ("remove-composite-tenant-index.v1", "Remove tenant composite index", "schema", "Simulate loss of the dominant tenant-scoped composite index.", ("tenant-skew-sensitivity.v1", "aggregate-report.v1")),
        ("increase-tenant-skew.v1", "Increase tenant skew", "data", "Concentrate most logical rows in the first tenant.", ()),
        ("expand-object-hydration.v1", "Expand object hydration", "application", "Increase columns and related collections materialized by reads.", ("relation-access-fanout.v1", "offset-pagination.v1")),
        ("extend-transaction-scope.v1", "Extend transaction scope", "runtime", "Place all operation queries inside one long transaction.", ()),
        ("stale-statistics.v1", "Stale statistics", "runtime", "Simulate cardinality-estimation uncertainty and plan instability.", ("tenant-skew-sensitivity.v1",)),
        ("increase-relation-fanout.v1", "Increase relation fan-out", "data", "Increase child rows per parent while preserving tenant isolation.", ("relation-access-fanout.v1", "nested-relation-fanout.v1")),
    )
    output = []
    for key, title, mutation_class, description, compatible in specs:
        payload = MutationDefinitionPayload(mutation_key=key, title=title, mutation_class=mutation_class, adapter_key="academic-lab.v1", compatible_template_keys=compatible, description=description)
        output.append(MutationDefinitionArtifact(created_at=semantic_epoch(), artifact_id=_stable("mut", payload, producer), producer=producer, provenance=Provenance(derivation_key="academic-mutation.v1"), payload=payload).seal())
    return tuple(output)
