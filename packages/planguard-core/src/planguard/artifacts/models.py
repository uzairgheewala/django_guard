"""Canonical PlanGuard artifact contracts through Milestone B.

The module intentionally keeps persisted contracts together so the generated
JSON Schema and TypeScript boundary are derived from one source of truth.
Runtime engines live in dedicated modules and consume these immutable models.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Generic, Literal, TypeAlias, TypeVar

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from planguard.canonical import canonical_data, content_hash
from planguard.ids import new_artifact_id, validate_artifact_id
from planguard.time import utc_now

JsonObject: TypeAlias = dict[str, Any]
JsonValue: TypeAlias = Any


class FrozenModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
        use_enum_values=False,
    )


class CapabilityState(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class RunStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INCOMPLETE = "incomplete"


class ParseQuality(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    FALLBACK = "fallback"
    FAILED = "failed"


class SeverityLevel(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConfidenceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvaluationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    WARNED = "warned"
    NOT_EVALUATED = "not_evaluated"


class DetectorStatus(StrEnum):
    EXECUTED = "executed"
    NOT_APPLICABLE = "not_applicable"
    NOT_EVALUATED = "not_evaluated"
    FAILED = "failed"
    CAPABILITY_MISSING = "capability_missing"


class ProducerIdentity(FrozenModel):
    name: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    build: str | None = Field(default=None, max_length=128)


class ArtifactReference(FrozenModel):
    artifact_id: str
    artifact_kind: str = Field(min_length=1, max_length=128)
    schema_version: str | None = Field(default=None, max_length=128)
    content_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")

    @field_validator("artifact_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_artifact_id(value)


class Provenance(FrozenModel):
    input_refs: tuple[ArtifactReference, ...] = ()
    configuration_ref: ArtifactReference | None = None
    code_revision: str | None = Field(default=None, max_length=256)
    derivation_key: str | None = Field(default=None, max_length=256)
    notes: tuple[str, ...] = ()


class CapabilityStatus(FrozenModel):
    state: CapabilityState
    reason: str | None = None
    details: JsonObject = Field(default_factory=dict)

    @field_validator("details")
    @classmethod
    def validate_details(cls, value: JsonObject) -> JsonObject:
        canonical_data(value)
        return value


class CapabilityGap(FrozenModel):
    capability: str = Field(min_length=1, max_length=256)
    status: Literal["unsupported", "partial", "unknown"]
    reason: str
    subject_ref: ArtifactReference | None = None
    impact: tuple[str, ...] = ()
    details: JsonObject = Field(default_factory=dict)

    @field_validator("details")
    @classmethod
    def validate_details(cls, value: JsonObject) -> JsonObject:
        canonical_data(value)
        return value


PayloadT = TypeVar("PayloadT", bound=BaseModel)


class ArtifactDocument(FrozenModel, Generic[PayloadT]):
    """Versioned immutable artifact envelope."""

    schema_version: str = Field(min_length=1, max_length=128)
    artifact_kind: str = Field(min_length=1, max_length=128)
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("art"))
    created_at: datetime = Field(default_factory=utc_now)
    producer: ProducerIdentity
    provenance: Provenance = Field(default_factory=Provenance)
    payload: PayloadT
    extensions: dict[str, JsonObject] = Field(default_factory=dict)
    content_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")

    @field_validator("artifact_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_artifact_id(value)

    @field_validator("created_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Artifact timestamps must be timezone-aware")
        return value

    @field_validator("extensions")
    @classmethod
    def validate_extensions(cls, value: dict[str, JsonObject]) -> dict[str, JsonObject]:
        for namespace, payload in value.items():
            if not namespace or namespace.startswith(".") or namespace.endswith("."):
                raise ValueError(f"Invalid extension namespace: {namespace!r}")
            canonical_data(payload)
        return value

    def hash_material(self) -> JsonObject:
        return self.model_dump(mode="python", exclude={"content_hash"}, exclude_none=False)

    def compute_content_hash(self) -> str:
        return content_hash(self.hash_material())

    def seal(self) -> "ArtifactDocument[PayloadT]":
        expected = self.compute_content_hash()
        if self.content_hash == expected:
            return self
        return self.model_copy(update={"content_hash": expected})

    def verify_integrity(self) -> bool:
        return self.content_hash is not None and self.content_hash == self.compute_content_hash()

    @model_validator(mode="after")
    def validate_existing_hash(self) -> "ArtifactDocument[PayloadT]":
        if self.content_hash is not None and not self.verify_integrity():
            raise ValueError("Artifact content_hash does not match canonical document content")
        return self

    def reference(self) -> ArtifactReference:
        return ArtifactReference(
            artifact_id=self.artifact_id,
            artifact_kind=self.artifact_kind,
            schema_version=self.schema_version,
            content_hash=self.content_hash,
        )


# ---------------------------------------------------------------------------
# Milestone A contracts retained without breaking v1 persisted documents.
# ---------------------------------------------------------------------------


class RunSummary(FrozenModel):
    name: str = Field(min_length=1, max_length=256)
    mode: str = Field(min_length=1, max_length=64)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: RunStatus
    tags: tuple[str, ...] = ()


class ArtifactInventory(FrozenModel):
    by_kind: dict[str, int] = Field(default_factory=dict)
    total_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_total(self) -> "ArtifactInventory":
        if sum(self.by_kind.values()) != self.total_count:
            raise ValueError("Artifact inventory total_count must equal the by_kind sum")
        if any(count < 0 for count in self.by_kind.values()):
            raise ValueError("Artifact inventory counts must be non-negative")
        return self


class BundleIntegrity(FrozenModel):
    bundle_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    verified: bool = False
    missing_refs: tuple[ArtifactReference, ...] = ()


class RunManifestPayload(FrozenModel):
    run: RunSummary
    environment_ref: ArtifactReference | None = None
    capture_policy_ref: ArtifactReference | None = None
    scenario_instance_ref: ArtifactReference | None = None
    artifact_inventory: ArtifactInventory = Field(default_factory=ArtifactInventory)
    capability_status: dict[str, CapabilityStatus] = Field(default_factory=dict)
    capability_gap_refs: tuple[ArtifactReference, ...] = ()
    integrity: BundleIntegrity = Field(default_factory=BundleIntegrity)


class RuntimeComponent(FrozenModel):
    name: str
    version: str | None = None
    details: JsonObject = Field(default_factory=dict)


class DatabaseIdentity(FrozenModel):
    vendor: str = "unknown"
    version: str | None = None
    database_hash: str | None = None
    connection_aliases: tuple[str, ...] = ()


class EnvironmentProfilePayload(FrozenModel):
    operating_system: str | None = None
    architecture: str | None = None
    python_version: str
    runtime_components: tuple[RuntimeComponent, ...] = ()
    database: DatabaseIdentity = Field(default_factory=DatabaseIdentity)
    environment_variables: dict[str, str] = Field(default_factory=dict)
    machine_profile: JsonObject = Field(default_factory=dict)
    notes: tuple[str, ...] = ()


class RawSqlMode(StrEnum):
    OMIT = "omit"
    REDACT = "redact"
    PRESERVE = "preserve"


class ParameterCaptureMode(StrEnum):
    NONE = "none"
    SHAPE = "shape"
    SHAPE_AND_HASH = "shape_and_hash"
    PRESERVE = "preserve"


class OriginCaptureMode(StrEnum):
    NONE = "none"
    FIRST_APPLICATION_FRAME = "first_application_frame"
    TRIMMED_APPLICATION_STACK = "trimmed_application_stack"
    FULL_STACK = "full_stack"


class CaptureLimits(FrozenModel):
    max_query_count: int = Field(default=100_000, ge=0)
    max_raw_sql_bytes: int = Field(default=1_000_000, ge=0)
    max_stack_depth: int = Field(default=32, ge=0)
    max_artifact_bytes: int = Field(default=100_000_000, ge=0)


class CapturePolicyPayload(FrozenModel):
    policy_key: str = Field(min_length=1, max_length=256)
    raw_sql_mode: RawSqlMode = RawSqlMode.REDACT
    parameter_capture_mode: ParameterCaptureMode = ParameterCaptureMode.SHAPE_AND_HASH
    origin_capture_mode: OriginCaptureMode = OriginCaptureMode.FIRST_APPLICATION_FRAME
    include_connection_aliases: tuple[str, ...] = ()
    exclude_module_patterns: tuple[str, ...] = ()
    application_roots: tuple[str, ...] = ()
    limits: CaptureLimits = Field(default_factory=CaptureLimits)
    hmac_key_id: str | None = None
    notes: tuple[str, ...] = ()


class CapabilityGapPayload(FrozenModel):
    gaps: tuple[CapabilityGap, ...]


# ---------------------------------------------------------------------------
# Capture and query observation contracts.
# ---------------------------------------------------------------------------


class SourceFrame(FrozenModel):
    module: str | None = None
    file: str | None = None
    line: int | None = Field(default=None, ge=1)
    function: str | None = None


class QueryOrigin(FrozenModel):
    application_frame: SourceFrame | None = None
    stack: tuple[SourceFrame, ...] = ()
    stack_fingerprint: str | None = None


class ParameterDescriptor(FrozenModel):
    type_name: str
    container: str | None = None
    length: int | None = Field(default=None, ge=0)
    value_hash: str | None = None
    preserved_value: JsonValue | None = None

    @field_validator("preserved_value")
    @classmethod
    def validate_preserved_value(cls, value: JsonValue | None) -> JsonValue | None:
        canonical_data(value)
        return value


class QueryConnection(FrozenModel):
    alias: str
    vendor: str = "unknown"


class QueryTiming(FrozenModel):
    started_offset_ms: float = Field(ge=0)
    duration_ms: float = Field(ge=0)


class QueryTransaction(FrozenModel):
    transaction_id: str | None = None
    depth: int = Field(default=0, ge=0)
    autocommit: bool | None = None


class QueryOutcome(FrozenModel):
    status: Literal["succeeded", "failed"]
    row_count: int | None = None
    exception_type: str | None = None
    exception_message: str | None = None


class QueryExecutionPayload(FrozenModel):
    run_id: str
    sequence_number: int = Field(ge=1)
    connection: QueryConnection
    timing: QueryTiming
    raw_sql_mode: RawSqlMode
    sql: str | None = None
    parameters: tuple[ParameterDescriptor, ...] = ()
    parameter_binding_fingerprint: str | None = None
    origin: QueryOrigin = Field(default_factory=QueryOrigin)
    transaction: QueryTransaction = Field(default_factory=QueryTransaction)
    outcome: QueryOutcome
    many: bool = False
    context: JsonObject = Field(default_factory=dict)

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        return validate_artifact_id(value)


class QueryFeatures(FrozenModel):
    statement_kind: str = "unknown"
    relations: tuple[str, ...] = ()
    projected_columns: tuple[str, ...] = ()
    predicate_columns: tuple[str, ...] = ()
    join_count: int = Field(default=0, ge=0)
    aggregate_count: int = Field(default=0, ge=0)
    has_group_by: bool = False
    has_order_by: bool = False
    has_limit: bool = False
    has_offset: bool = False
    has_cte: bool = False
    has_subquery: bool = False
    has_locking_clause: bool = False


class QueryTemplatePayload(FrozenModel):
    dialect: str
    canonical_sql: str
    lexical_fingerprint: str
    structural_shape_fingerprint: str
    statement_kind: str
    features: QueryFeatures = Field(default_factory=QueryFeatures)
    parse_quality: ParseQuality
    diagnostics: tuple[str, ...] = ()


class FamilySchemePayload(FrozenModel):
    family_scheme_key: str
    title: str
    dimensions: tuple[str, ...]
    missing_value_policy: Literal["preserve_unknown", "reject", "omit_dimension"] = (
        "preserve_unknown"
    )
    description: str | None = None


class ParameterRegime(FrozenModel):
    regime_key: str
    member_count: int = Field(ge=0)
    details: JsonObject = Field(default_factory=dict)


class FamilyAggregates(FrozenModel):
    execution_count: int = Field(ge=0)
    distinct_parameter_bindings: int = Field(ge=0)
    total_duration_ms: float = Field(ge=0)
    mean_duration_ms: float = Field(ge=0)
    median_duration_ms: float = Field(ge=0)
    maximum_duration_ms: float = Field(ge=0)
    failed_execution_count: int = Field(default=0, ge=0)


class FamilyTemporalRange(FrozenModel):
    first_sequence: int = Field(ge=1)
    last_sequence: int = Field(ge=1)
    span_ms: float = Field(ge=0)


class ObservedQueryFamilyPayload(FrozenModel):
    run_id: str
    family_scheme_key: str
    query_template_ref: ArtifactReference
    dimension_values: dict[str, str]
    member_execution_refs: tuple[ArtifactReference, ...]
    aggregates: FamilyAggregates
    temporal: FamilyTemporalRange
    parameter_regimes: tuple[ParameterRegime, ...] = ()

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        return validate_artifact_id(value)


# ---------------------------------------------------------------------------
# Analysis, detector, evidence, and finding contracts.
# ---------------------------------------------------------------------------


class EvidenceClaim(FrozenModel):
    claim_key: str
    status: Literal["supported", "contradicted", "unknown"]
    subject_refs: tuple[ArtifactReference, ...] = ()
    values: JsonObject = Field(default_factory=dict)
    explanation: str | None = None


class EvidencePayload(FrozenModel):
    run_id: str
    claims: tuple[EvidenceClaim, ...]

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        return validate_artifact_id(value)


class Score(FrozenModel):
    level: SeverityLevel | ConfidenceLevel
    score: float = Field(ge=0, le=1)


class FindingExplanation(FrozenModel):
    summary: str
    details: tuple[str, ...] = ()


class RemediationGuidance(FrozenModel):
    category: str
    guidance: tuple[str, ...] = ()


class FindingPayload(FrozenModel):
    run_id: str
    detector_key: str
    mechanism_key: str
    title: str
    severity: Score
    confidence: Score
    subject_refs: tuple[ArtifactReference, ...]
    evidence_refs: tuple[ArtifactReference, ...] = ()
    claims: tuple[EvidenceClaim, ...] = ()
    explanation: FindingExplanation
    remediation: RemediationGuidance
    limitations: tuple[str, ...] = ()
    metadata: JsonObject = Field(default_factory=dict)

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        return validate_artifact_id(value)


class DetectorReceiptPayload(FrozenModel):
    run_id: str
    detector_key: str
    detector_version: str
    status: DetectorStatus
    started_at: datetime
    completed_at: datetime
    finding_refs: tuple[ArtifactReference, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    missing_capabilities: tuple[str, ...] = ()
    error: str | None = None
    statistics: JsonObject = Field(default_factory=dict)

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        return validate_artifact_id(value)


# ---------------------------------------------------------------------------
# Generic selector and policy contracts.
# ---------------------------------------------------------------------------


class SelectorOperator(StrEnum):
    ALL = "all"
    ANY = "any"
    NOT = "not"
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_OR_EQUAL = "greater_or_equal"
    LESS_THAN = "less_than"
    LESS_OR_EQUAL = "less_or_equal"
    CONTAINS = "contains"
    EXISTS = "exists"
    IN_SET = "in_set"


class SelectorExpression(FrozenModel):
    operator: SelectorOperator
    field: str | None = None
    value: JsonValue | None = None
    children: tuple["SelectorExpression", ...] = ()

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: JsonValue | None) -> JsonValue | None:
        canonical_data(value)
        return value

    @model_validator(mode="after")
    def validate_shape(self) -> "SelectorExpression":
        logical = {SelectorOperator.ALL, SelectorOperator.ANY, SelectorOperator.NOT}
        if self.operator in logical:
            if not self.children:
                raise ValueError(f"{self.operator} requires children")
            if self.operator == SelectorOperator.NOT and len(self.children) != 1:
                raise ValueError("not requires exactly one child")
        elif not self.field:
            raise ValueError(f"{self.operator} requires a field")
        return self


class BudgetRule(FrozenModel):
    rule_key: str
    subject_kind: Literal["run", "family", "finding", "detector_receipt", "comparison", "plan"]
    metric: str | None = None
    selector: SelectorExpression | None = None
    operator: Literal[
        "less_or_equal",
        "less_than",
        "greater_or_equal",
        "greater_than",
        "equals",
        "no_matches",
        "has_matches",
    ]
    threshold: float | int | str | None = None
    disposition: Literal["fail", "warn"] = "fail"
    message: str | None = None


class BudgetPolicyPayload(FrozenModel):
    policy_key: str
    title: str
    rules: tuple[BudgetRule, ...]
    description: str | None = None
    tags: tuple[str, ...] = ()


class RuleEvaluation(FrozenModel):
    rule_key: str
    status: EvaluationStatus
    measured_value: JsonValue | None = None
    threshold: JsonValue | None = None
    matched_subject_refs: tuple[ArtifactReference, ...] = ()
    evidence_refs: tuple[ArtifactReference, ...] = ()
    message: str

    @field_validator("measured_value", "threshold")
    @classmethod
    def validate_json_value(cls, value: JsonValue | None) -> JsonValue | None:
        canonical_data(value)
        return value


class BudgetEvaluationPayload(FrozenModel):
    run_id: str
    policy_ref: ArtifactReference
    status: EvaluationStatus
    rule_evaluations: tuple[RuleEvaluation, ...]
    evaluated_at: datetime

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        return validate_artifact_id(value)


class AnalysisSummaryPayload(FrozenModel):
    run_id: str
    query_count: int = Field(ge=0)
    query_template_count: int = Field(ge=0)
    family_count_by_scheme: dict[str, int] = Field(default_factory=dict)
    total_database_time_ms: float = Field(ge=0)
    finding_count_by_severity: dict[str, int] = Field(default_factory=dict)
    query_execution_refs: tuple[ArtifactReference, ...] = ()
    query_template_refs: tuple[ArtifactReference, ...] = ()
    family_refs: tuple[ArtifactReference, ...] = ()
    evidence_refs: tuple[ArtifactReference, ...] = ()
    finding_refs: tuple[ArtifactReference, ...] = ()
    detector_receipt_refs: tuple[ArtifactReference, ...] = ()
    budget_evaluation_refs: tuple[ArtifactReference, ...] = ()

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        return validate_artifact_id(value)



# ---------------------------------------------------------------------------
# Milestone C workload graph, motif, and episode contracts.
# ---------------------------------------------------------------------------


class WorkloadNodeKind(StrEnum):
    OPERATION = "operation"
    QUERY_EXECUTION = "query_execution"
    QUERY_FAMILY = "query_family"
    TRANSACTION = "transaction"
    FINDING = "finding"
    EVIDENCE = "evidence"
    EPISODE = "episode"


class WorkloadEdgeKind(StrEnum):
    CONTAINS = "contains"
    EMITS = "emits"
    MEMBER_OF = "member_of"
    TEMPORALLY_PRECEDES = "temporally_precedes"
    SAME_ORIGIN = "same_origin"
    SAME_TRANSACTION = "same_transaction"
    REPEATED_WITHIN = "repeated_within"
    POSSIBLE_RESULT_DRIVES = "possible_result_drives"
    SUPPORTS = "supports"
    AFFECTS = "affects"
    MATCHES_MOTIF = "matches_motif"


class InferenceMethod(StrEnum):
    OBSERVED = "observed"
    DERIVED = "derived"
    INFERRED = "inferred"


class WorkloadNode(FrozenModel):
    node_id: str = Field(min_length=1, max_length=256)
    kind: WorkloadNodeKind
    label: str = Field(min_length=1, max_length=512)
    artifact_ref: ArtifactReference | None = None
    attributes: JsonObject = Field(default_factory=dict)

    @field_validator("attributes")
    @classmethod
    def validate_attributes(cls, value: JsonObject) -> JsonObject:
        canonical_data(value)
        return value


class WorkloadEdge(FrozenModel):
    edge_id: str = Field(min_length=1, max_length=256)
    from_node: str = Field(min_length=1, max_length=256)
    to_node: str = Field(min_length=1, max_length=256)
    kind: WorkloadEdgeKind
    confidence: float = Field(default=1.0, ge=0, le=1)
    inference_method: InferenceMethod = InferenceMethod.OBSERVED
    evidence_refs: tuple[ArtifactReference, ...] = ()
    attributes: JsonObject = Field(default_factory=dict)

    @field_validator("attributes")
    @classmethod
    def validate_edge_attributes(cls, value: JsonObject) -> JsonObject:
        canonical_data(value)
        return value


class WorkloadGraphPayload(FrozenModel):
    run_id: str
    family_scheme_key: str
    graph_version: str = "workload-graph.v1"
    nodes: tuple[WorkloadNode, ...]
    edges: tuple[WorkloadEdge, ...]
    capability_gaps: tuple[str, ...] = ()

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        return validate_artifact_id(value)

    @model_validator(mode="after")
    def validate_graph(self) -> "WorkloadGraphPayload":
        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Workload graph node IDs must be unique")
        known = set(node_ids)
        edge_ids: set[str] = set()
        for edge in self.edges:
            if edge.edge_id in edge_ids:
                raise ValueError("Workload graph edge IDs must be unique")
            edge_ids.add(edge.edge_id)
            if edge.from_node not in known or edge.to_node not in known:
                raise ValueError("Workload graph edges must reference known nodes")
        return self


class MotifNodeRole(FrozenModel):
    role_key: str
    allowed_kinds: tuple[WorkloadNodeKind, ...]
    description: str | None = None


class MotifEdgePattern(FrozenModel):
    from_role: str
    to_role: str
    allowed_kinds: tuple[WorkloadEdgeKind, ...]
    minimum_confidence: float = Field(default=0.0, ge=0, le=1)


class MotifConstraintDefinition(FrozenModel):
    constraint_key: str
    kind: str
    parameters: JsonObject = Field(default_factory=dict)
    description: str | None = None


class WorkloadMotifPayload(FrozenModel):
    motif_key: str
    title: str
    description: str
    node_roles: tuple[MotifNodeRole, ...]
    edge_patterns: tuple[MotifEdgePattern, ...] = ()
    constraints: tuple[MotifConstraintDefinition, ...] = ()
    mechanism_keys: tuple[str, ...] = ()


class ConstraintEvaluation(FrozenModel):
    constraint_key: str
    status: Literal["satisfied", "not_satisfied", "unknown", "not_evaluated"]
    values: JsonObject = Field(default_factory=dict)
    explanation: str | None = None


class WorkloadEpisodePayload(FrozenModel):
    run_id: str
    motif_key: str
    title: str
    family_scheme_key: str
    node_bindings: dict[str, str]
    edge_ids: tuple[str, ...] = ()
    constraint_evaluations: tuple[ConstraintEvaluation, ...] = ()
    match_confidence: float = Field(ge=0, le=1)
    subject_refs: tuple[ArtifactReference, ...] = ()
    metadata: JsonObject = Field(default_factory=dict)

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        return validate_artifact_id(value)



# ---------------------------------------------------------------------------
# Milestone D generic scenario, dataset, mutation, and run contracts.
# ---------------------------------------------------------------------------


class ScenarioRoleKind(StrEnum):
    RELATIONAL_ENTITY = "relational_entity"
    APPLICATION_OPERATION = "application_operation"
    DATASET = "dataset"
    ENVIRONMENT = "environment"
    RESULT = "result"
    POLICY = "policy"
    OPAQUE = "opaque"


class ParameterDomainKind(StrEnum):
    FINITE = "finite"
    INTEGER_RANGE = "integer_range"
    FLOAT_RANGE = "float_range"
    PARTITIONED = "partitioned"
    REGISTRY = "registry"
    BOOLEAN = "boolean"
    OPAQUE = "opaque"


class ScenarioReceiptStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_EVALUATED = "not_evaluated"


class OracleStatus(StrEnum):
    SATISFIED = "satisfied"
    NOT_SATISFIED = "not_satisfied"
    UNKNOWN = "unknown"
    NOT_EVALUATED = "not_evaluated"


class ParameterPartition(FrozenModel):
    key: str
    title: str | None = None
    minimum: float | int | None = None
    maximum: float | int | None = None
    include_minimum: bool = True
    include_maximum: bool = True
    representative_values: tuple[JsonValue, ...] = ()

    @field_validator("representative_values")
    @classmethod
    def validate_representatives(cls, value: tuple[JsonValue, ...]) -> tuple[JsonValue, ...]:
        canonical_data(value)
        return value


class ParameterDomain(FrozenModel):
    kind: ParameterDomainKind
    values: tuple[JsonValue, ...] = ()
    minimum: float | int | None = None
    maximum: float | int | None = None
    step: float | int | None = None
    registry_key: str | None = None
    partitions: tuple[ParameterPartition, ...] = ()
    default: JsonValue | None = None
    constraints: tuple[SelectorExpression, ...] = ()

    @field_validator("values", "default")
    @classmethod
    def validate_json_values(cls, value):
        canonical_data(value)
        return value

    @model_validator(mode="after")
    def validate_domain(self) -> "ParameterDomain":
        if self.kind == ParameterDomainKind.FINITE and not self.values:
            raise ValueError("finite parameter domains require values")
        if self.kind in {ParameterDomainKind.INTEGER_RANGE, ParameterDomainKind.FLOAT_RANGE} and (
            self.minimum is None or self.maximum is None
        ):
            raise ValueError("numeric range domains require minimum and maximum")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("parameter domain minimum must not exceed maximum")
        if self.kind == ParameterDomainKind.REGISTRY and not self.registry_key:
            raise ValueError("registry parameter domains require registry_key")
        return self


class ScenarioRole(FrozenModel):
    role_key: str
    kind: ScenarioRoleKind
    required: bool = True
    cardinality: Literal["one", "optional_one", "many"] = "one"
    contract_key: str | None = None
    description: str | None = None


class ScenarioParameter(FrozenModel):
    parameter_key: str
    domain: ParameterDomain
    required: bool = True
    description: str | None = None
    tags: tuple[str, ...] = ()


class ScenarioOperationNode(FrozenModel):
    node_key: str
    kind: str
    role_ref: str | None = None
    phase: str | None = None
    attributes: JsonObject = Field(default_factory=dict)


class ScenarioOperationEdge(FrozenModel):
    from_node: str
    to_node: str
    kind: str
    attributes: JsonObject = Field(default_factory=dict)


class ScenarioVariant(FrozenModel):
    variant_key: str
    title: str
    implementation_role: str | None = None
    description: str | None = None
    tags: tuple[str, ...] = ()


class OracleDefinition(FrozenModel):
    oracle_key: str
    kind: str
    subject_selector: SelectorExpression | None = None
    parameters: JsonObject = Field(default_factory=dict)
    required_capabilities: tuple[str, ...] = ()
    disposition: Literal["fail", "warn", "record"] = "fail"
    description: str | None = None


class CoverageObligation(FrozenModel):
    obligation_key: str
    kind: str
    parameters: JsonObject = Field(default_factory=dict)
    description: str | None = None


class ScenarioTemplatePayload(FrozenModel):
    template_key: str
    title: str
    description: str
    roles: tuple[ScenarioRole, ...]
    parameters: tuple[ScenarioParameter, ...] = ()
    operation_nodes: tuple[ScenarioOperationNode, ...] = ()
    operation_edges: tuple[ScenarioOperationEdge, ...] = ()
    variants: tuple[ScenarioVariant, ...]
    oracles: tuple[OracleDefinition, ...] = ()
    coverage_obligations: tuple[CoverageObligation, ...] = ()
    compatible_template_keys: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_template(self) -> "ScenarioTemplatePayload":
        role_keys = [item.role_key for item in self.roles]
        parameter_keys = [item.parameter_key for item in self.parameters]
        variant_keys = [item.variant_key for item in self.variants]
        node_keys = [item.node_key for item in self.operation_nodes]
        for label, values in (("role", role_keys), ("parameter", parameter_keys), ("variant", variant_keys), ("node", node_keys)):
            if len(values) != len(set(values)):
                raise ValueError(f"Scenario {label} keys must be unique")
        known_roles = set(role_keys)
        known_nodes = set(node_keys)
        for node in self.operation_nodes:
            if node.role_ref and node.role_ref not in known_roles:
                raise ValueError(f"Operation node references unknown role: {node.role_ref}")
        for edge in self.operation_edges:
            if edge.from_node not in known_nodes or edge.to_node not in known_nodes:
                raise ValueError("Operation edges must reference known nodes")
        return self


class RoleBinding(FrozenModel):
    role_key: str
    binding_kind: Literal["model", "callable", "dataset", "value", "adapter", "opaque"]
    target: str
    configuration: JsonObject = Field(default_factory=dict)


class VariantBinding(FrozenModel):
    variant_key: str
    target: str
    configuration: JsonObject = Field(default_factory=dict)


class ScenarioBindingPayload(FrozenModel):
    binding_key: str
    template_ref: ArtifactReference
    application_key: str
    role_bindings: tuple[RoleBinding, ...]
    variant_bindings: tuple[VariantBinding, ...]
    adapter_key: str
    capabilities: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_binding_keys(self) -> "ScenarioBindingPayload":
        roles = [item.role_key for item in self.role_bindings]
        variants = [item.variant_key for item in self.variant_bindings]
        if len(roles) != len(set(roles)) or len(variants) != len(set(variants)):
            raise ValueError("Scenario binding keys must be unique")
        return self


class DistributionSpec(FrozenModel):
    distribution_key: str
    kind: str
    parameters: JsonObject = Field(default_factory=dict)
    seed_offset: int = 0


class DatasetManifestPayload(FrozenModel):
    dataset_key: str
    dataset_version: str
    generator_key: str
    seed: int
    scale_profile: str
    entity_counts: dict[str, int]
    distributions: tuple[DistributionSpec, ...] = ()
    constraints: tuple[str, ...] = ()
    dataset_fingerprint: str
    tenant_count: int = Field(default=1, ge=1)
    metadata: JsonObject = Field(default_factory=dict)

    @field_validator("entity_counts")
    @classmethod
    def validate_counts(cls, value: dict[str, int]) -> dict[str, int]:
        if any(item < 0 for item in value.values()):
            raise ValueError("Dataset entity counts must be non-negative")
        return value


class MutationDefinitionPayload(FrozenModel):
    mutation_key: str
    title: str
    mutation_class: Literal["application", "schema", "data", "runtime", "workload"]
    adapter_key: str
    parameter_domain: dict[str, ParameterDomain] = Field(default_factory=dict)
    compatible_template_keys: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    reversible: bool = True
    description: str | None = None


class AppliedMutation(FrozenModel):
    mutation_ref: ArtifactReference
    parameter_bindings: JsonObject = Field(default_factory=dict)
    order: int = Field(ge=0)


class ScenarioInstancePayload(FrozenModel):
    template_ref: ArtifactReference
    binding_ref: ArtifactReference
    parameter_bindings: JsonObject
    variant_key: str
    applied_mutations: tuple[AppliedMutation, ...] = ()
    seed: int
    series_key: str | None = None
    composed_from_refs: tuple[ArtifactReference, ...] = ()
    projected_dimensions: tuple[str, ...] = ()
    expected_capabilities: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    @field_validator("parameter_bindings")
    @classmethod
    def validate_parameter_bindings(cls, value: JsonObject) -> JsonObject:
        canonical_data(value)
        return value


class ScenarioSeriesPayload(FrozenModel):
    series_key: str
    template_ref: ArtifactReference
    binding_ref: ArtifactReference
    independent_dimensions: tuple[str, ...]
    instance_refs: tuple[ArtifactReference, ...]
    generation_strategy: str
    seed: int
    metadata: JsonObject = Field(default_factory=dict)


class ScenarioPhaseReceiptPayload(FrozenModel):
    scenario_instance_ref: ArtifactReference
    scenario_run_id: str
    phase_key: str
    status: ScenarioReceiptStatus
    started_at: datetime
    completed_at: datetime
    input_refs: tuple[ArtifactReference, ...] = ()
    output_refs: tuple[ArtifactReference, ...] = ()
    capability_gaps: tuple[str, ...] = ()
    error: str | None = None
    statistics: JsonObject = Field(default_factory=dict)

    @field_validator("scenario_run_id")
    @classmethod
    def validate_scenario_run_id(cls, value: str) -> str:
        return validate_artifact_id(value)


class OracleEvaluation(FrozenModel):
    oracle_key: str
    status: OracleStatus
    measured_value: JsonValue | None = None
    expected_value: JsonValue | None = None
    evidence_refs: tuple[ArtifactReference, ...] = ()
    explanation: str

    @field_validator("measured_value", "expected_value")
    @classmethod
    def validate_oracle_values(cls, value):
        canonical_data(value)
        return value


class ScenarioRunPayload(FrozenModel):
    scenario_run_id: str
    scenario_instance_ref: ArtifactReference
    dataset_ref: ArtifactReference | None = None
    analysis_run_ref: ArtifactReference | None = None
    status: ScenarioReceiptStatus
    variant_key: str
    phase_receipt_refs: tuple[ArtifactReference, ...]
    oracle_evaluations: tuple[OracleEvaluation, ...] = ()
    result_digest: str | None = None
    state_digest: str | None = None
    started_at: datetime
    completed_at: datetime
    capability_gaps: tuple[str, ...] = ()
    metadata: JsonObject = Field(default_factory=dict)

    @field_validator("scenario_run_id")
    @classmethod
    def validate_scenario_run_id(cls, value: str) -> str:
        return validate_artifact_id(value)



# ---------------------------------------------------------------------------
# Milestone E PostgreSQL plan and comparison contracts.
# ---------------------------------------------------------------------------


class PlanCollectionMode(StrEnum):
    DISABLED = "disabled"
    ESTIMATED_ONLY = "estimated_only"
    ANALYZE_SAFE_SELECTS = "analyze_safe_selects"
    EXPLICIT_ALLOWLIST = "explicit_allowlist"
    IMPORTED = "imported"


class PlanCollectionStatus(StrEnum):
    COLLECTED = "collected"
    SKIPPED = "skipped"
    REJECTED = "rejected"
    FAILED = "failed"
    CAPABILITY_MISSING = "capability_missing"


class PlanNode(FrozenModel):
    node_id: str
    node_type: str
    relation: str | None = None
    alias: str | None = None
    index: str | None = None
    join_type: str | None = None
    strategy: str | None = None
    estimated_startup_cost: float | None = Field(default=None, ge=0)
    estimated_total_cost: float | None = Field(default=None, ge=0)
    estimated_rows: float | None = Field(default=None, ge=0)
    estimated_width: int | None = Field(default=None, ge=0)
    actual_startup_ms: float | None = Field(default=None, ge=0)
    actual_total_ms: float | None = Field(default=None, ge=0)
    actual_rows: float | None = Field(default=None, ge=0)
    loops: float | None = Field(default=None, ge=0)
    rows_removed_by_filter: float | None = Field(default=None, ge=0)
    shared_hit_blocks: int | None = Field(default=None, ge=0)
    shared_read_blocks: int | None = Field(default=None, ge=0)
    temp_read_blocks: int | None = Field(default=None, ge=0)
    temp_written_blocks: int | None = Field(default=None, ge=0)
    sort_method: str | None = None
    sort_space_type: str | None = None
    sort_space_kb: int | None = Field(default=None, ge=0)
    peak_memory_kb: int | None = Field(default=None, ge=0)
    workers_planned: int | None = Field(default=None, ge=0)
    workers_launched: int | None = Field(default=None, ge=0)
    filter: str | None = None
    index_condition: str | None = None
    hash_condition: str | None = None
    join_filter: str | None = None
    child_node_ids: tuple[str, ...] = ()
    unknown_attributes: JsonObject = Field(default_factory=dict)

    @field_validator("unknown_attributes")
    @classmethod
    def validate_unknown_plan_attributes(cls, value: JsonObject) -> JsonObject:
        canonical_data(value)
        return value


class PlanFeatures(FrozenModel):
    node_count: int = Field(ge=0)
    maximum_depth: int = Field(ge=0)
    node_type_counts: dict[str, int] = Field(default_factory=dict)
    relation_access: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    index_names: tuple[str, ...] = ()
    maximum_estimate_error_ratio: float | None = Field(default=None, ge=0)
    nested_loop_effective_rows: float | None = Field(default=None, ge=0)
    rows_removed_by_filter: float = Field(default=0, ge=0)
    shared_hit_blocks: int = Field(default=0, ge=0)
    shared_read_blocks: int = Field(default=0, ge=0)
    temporary_io_blocks: int = Field(default=0, ge=0)
    has_disk_spill: bool = False
    has_parallelism: bool = False
    planning_time_ms: float | None = Field(default=None, ge=0)
    execution_time_ms: float | None = Field(default=None, ge=0)
    plan_shape_fingerprint: str


class PlanCollectionContext(FrozenModel):
    mode: PlanCollectionMode
    analyzed: bool
    statement_timeout_ms: int | None = Field(default=None, ge=1)
    representative_strategy: Literal["first", "slowest", "median_duration", "explicit", "imported"]
    cache_protocol: Literal["unknown", "cold", "warm", "cold_then_warm", "mixed"] = "unknown"
    server_version: str | None = None
    database_settings: JsonObject = Field(default_factory=dict)
    collection_notes: tuple[str, ...] = ()


class PlanObservationPayload(FrozenModel):
    run_id: str
    query_family_ref: ArtifactReference
    representative_execution_ref: ArtifactReference | None = None
    parameter_regime_key: str | None = None
    collection: PlanCollectionContext
    root_node_id: str
    nodes: tuple[PlanNode, ...]
    features: PlanFeatures
    raw_plan: JsonObject
    warnings: tuple[str, ...] = ()
    capability_gaps: tuple[str, ...] = ()

    @field_validator("run_id")
    @classmethod
    def validate_plan_run_id(cls, value: str) -> str:
        return validate_artifact_id(value)

    @field_validator("raw_plan")
    @classmethod
    def validate_raw_plan(cls, value: JsonObject) -> JsonObject:
        canonical_data(value)
        return value

    @model_validator(mode="after")
    def validate_plan_tree(self) -> "PlanObservationPayload":
        ids = [node.node_id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("Plan node IDs must be unique")
        known = set(ids)
        if self.root_node_id not in known:
            raise ValueError("Plan root_node_id must reference a known node")
        for node in self.nodes:
            if any(child not in known for child in node.child_node_ids):
                raise ValueError("Plan child_node_ids must reference known nodes")
        return self


class PlanCollectionReceiptPayload(FrozenModel):
    run_id: str
    query_family_ref: ArtifactReference
    status: PlanCollectionStatus
    mode: PlanCollectionMode
    started_at: datetime
    completed_at: datetime
    plan_ref: ArtifactReference | None = None
    representative_execution_ref: ArtifactReference | None = None
    safety_checks: JsonObject = Field(default_factory=dict)
    error: str | None = None
    notes: tuple[str, ...] = ()

    @field_validator("run_id")
    @classmethod
    def validate_receipt_run_id(cls, value: str) -> str:
        return validate_artifact_id(value)


class ComparabilityState(StrEnum):
    IDENTICAL = "identical"
    COMPATIBLE = "compatible"
    CONTROLLED_CHANGE = "controlled_change"
    CONFOUNDING_CHANGE = "confounding_change"
    UNKNOWN = "unknown"


class ComparisonStatus(StrEnum):
    VALID = "valid"
    VALID_WITH_CONTROLLED_CHANGES = "valid_with_controlled_changes"
    DEGRADED = "degraded"
    INVALID = "invalid"


class DimensionAssessment(FrozenModel):
    dimension_key: str
    state: ComparabilityState
    baseline_value: JsonValue | None = None
    candidate_value: JsonValue | None = None
    explanation: str
    affects: tuple[Literal["correctness", "structure", "plans", "resources", "timing"], ...] = ()

    @field_validator("baseline_value", "candidate_value")
    @classmethod
    def validate_dimension_values(cls, value: JsonValue | None) -> JsonValue | None:
        canonical_data(value)
        return value


class MetricDelta(FrozenModel):
    metric_key: str
    baseline: float | int | None = None
    candidate: float | int | None = None
    absolute_delta: float | int | None = None
    relative_delta: float | None = None
    unit: str | None = None
    direction: Literal["improved", "regressed", "unchanged", "unknown"] = "unknown"
    validity: Literal["valid", "advisory", "not_comparable", "not_available"] = "valid"
    explanation: str | None = None


class FamilyChange(FrozenModel):
    change_kind: Literal["added", "removed", "changed", "split", "merged", "unchanged"]
    baseline_family_refs: tuple[ArtifactReference, ...] = ()
    candidate_family_refs: tuple[ArtifactReference, ...] = ()
    structural_shape_fingerprint: str | None = None
    deltas: tuple[MetricDelta, ...] = ()
    explanation: str


class PlanChange(FrozenModel):
    change_kind: Literal["added", "removed", "changed", "unchanged", "not_comparable"]
    baseline_plan_ref: ArtifactReference | None = None
    candidate_plan_ref: ArtifactReference | None = None
    query_shape_fingerprint: str | None = None
    transitions: tuple[str, ...] = ()
    deltas: tuple[MetricDelta, ...] = ()
    severity: SeverityLevel = SeverityLevel.INFO
    explanation: str


class FindingChange(FrozenModel):
    change_kind: Literal["introduced", "resolved", "changed", "unchanged"]
    mechanism_key: str
    baseline_finding_refs: tuple[ArtifactReference, ...] = ()
    candidate_finding_refs: tuple[ArtifactReference, ...] = ()
    explanation: str


class RelativeRuleEvaluation(FrozenModel):
    rule_key: str
    status: EvaluationStatus
    metric_key: str | None = None
    measured_value: JsonValue | None = None
    threshold: JsonValue | None = None
    subject_refs: tuple[ArtifactReference, ...] = ()
    message: str


class ComparisonReportPayload(FrozenModel):
    baseline_run_ref: ArtifactReference
    candidate_run_ref: ArtifactReference
    status: ComparisonStatus
    dimensions: tuple[DimensionAssessment, ...]
    changed_dimensions: tuple[str, ...] = ()
    metric_deltas: tuple[MetricDelta, ...] = ()
    family_changes: tuple[FamilyChange, ...] = ()
    plan_changes: tuple[PlanChange, ...] = ()
    finding_changes: tuple[FindingChange, ...] = ()
    relative_policy_ref: ArtifactReference | None = None
    relative_rule_evaluations: tuple[RelativeRuleEvaluation, ...] = ()
    narrative: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Concrete artifacts.
# ---------------------------------------------------------------------------


class RunManifestArtifact(ArtifactDocument[RunManifestPayload]):
    schema_version: Literal["planguard.run-manifest.v1"] = "planguard.run-manifest.v1"
    artifact_kind: Literal["run_manifest"] = "run_manifest"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("run"))


class EnvironmentProfileArtifact(ArtifactDocument[EnvironmentProfilePayload]):
    schema_version: Literal["planguard.environment-profile.v1"] = (
        "planguard.environment-profile.v1"
    )
    artifact_kind: Literal["environment_profile"] = "environment_profile"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("env"))


class CapturePolicyArtifact(ArtifactDocument[CapturePolicyPayload]):
    schema_version: Literal["planguard.capture-policy.v1"] = "planguard.capture-policy.v1"
    artifact_kind: Literal["capture_policy"] = "capture_policy"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("cap"))


class CapabilityGapArtifact(ArtifactDocument[CapabilityGapPayload]):
    schema_version: Literal["planguard.capability-gap.v1"] = "planguard.capability-gap.v1"
    artifact_kind: Literal["capability_gap"] = "capability_gap"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("gap"))


class QueryExecutionArtifact(ArtifactDocument[QueryExecutionPayload]):
    schema_version: Literal["planguard.query-execution.v1"] = "planguard.query-execution.v1"
    artifact_kind: Literal["query_execution"] = "query_execution"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("qexec"))


class QueryTemplateArtifact(ArtifactDocument[QueryTemplatePayload]):
    schema_version: Literal["planguard.query-template.v1"] = "planguard.query-template.v1"
    artifact_kind: Literal["query_template"] = "query_template"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("qtpl"))


class FamilySchemeArtifact(ArtifactDocument[FamilySchemePayload]):
    schema_version: Literal["planguard.family-scheme.v1"] = "planguard.family-scheme.v1"
    artifact_kind: Literal["family_scheme"] = "family_scheme"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("fsch"))


class ObservedQueryFamilyArtifact(ArtifactDocument[ObservedQueryFamilyPayload]):
    schema_version: Literal["planguard.observed-query-family.v1"] = (
        "planguard.observed-query-family.v1"
    )
    artifact_kind: Literal["observed_query_family"] = "observed_query_family"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("qfam"))


class EvidenceArtifact(ArtifactDocument[EvidencePayload]):
    schema_version: Literal["planguard.evidence.v1"] = "planguard.evidence.v1"
    artifact_kind: Literal["evidence"] = "evidence"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("evd"))


class FindingArtifact(ArtifactDocument[FindingPayload]):
    schema_version: Literal["planguard.finding.v1"] = "planguard.finding.v1"
    artifact_kind: Literal["finding"] = "finding"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("fnd"))


class DetectorReceiptArtifact(ArtifactDocument[DetectorReceiptPayload]):
    schema_version: Literal["planguard.detector-receipt.v1"] = (
        "planguard.detector-receipt.v1"
    )
    artifact_kind: Literal["detector_receipt"] = "detector_receipt"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("drc"))


class BudgetPolicyArtifact(ArtifactDocument[BudgetPolicyPayload]):
    schema_version: Literal["planguard.budget-policy.v1"] = "planguard.budget-policy.v1"
    artifact_kind: Literal["budget_policy"] = "budget_policy"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("bpol"))


class BudgetEvaluationArtifact(ArtifactDocument[BudgetEvaluationPayload]):
    schema_version: Literal["planguard.budget-evaluation.v1"] = (
        "planguard.budget-evaluation.v1"
    )
    artifact_kind: Literal["budget_evaluation"] = "budget_evaluation"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("beval"))


class AnalysisSummaryArtifact(ArtifactDocument[AnalysisSummaryPayload]):
    schema_version: Literal["planguard.analysis-summary.v1"] = (
        "planguard.analysis-summary.v1"
    )
    artifact_kind: Literal["analysis_summary"] = "analysis_summary"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("asum"))



class WorkloadGraphArtifact(ArtifactDocument[WorkloadGraphPayload]):
    schema_version: Literal["planguard.workload-graph.v1"] = "planguard.workload-graph.v1"
    artifact_kind: Literal["workload_graph"] = "workload_graph"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("wkg"))


class WorkloadMotifArtifact(ArtifactDocument[WorkloadMotifPayload]):
    schema_version: Literal["planguard.workload-motif.v1"] = "planguard.workload-motif.v1"
    artifact_kind: Literal["workload_motif"] = "workload_motif"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("wmotif"))


class WorkloadEpisodeArtifact(ArtifactDocument[WorkloadEpisodePayload]):
    schema_version: Literal["planguard.workload-episode.v1"] = "planguard.workload-episode.v1"
    artifact_kind: Literal["workload_episode"] = "workload_episode"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("wep"))



class ScenarioTemplateArtifact(ArtifactDocument[ScenarioTemplatePayload]):
    schema_version: Literal["planguard.scenario-template.v1"] = "planguard.scenario-template.v1"
    artifact_kind: Literal["scenario_template"] = "scenario_template"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("sct"))


class ScenarioBindingArtifact(ArtifactDocument[ScenarioBindingPayload]):
    schema_version: Literal["planguard.scenario-binding.v1"] = "planguard.scenario-binding.v1"
    artifact_kind: Literal["scenario_binding"] = "scenario_binding"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("scb"))


class ScenarioInstanceArtifact(ArtifactDocument[ScenarioInstancePayload]):
    schema_version: Literal["planguard.scenario-instance.v1"] = "planguard.scenario-instance.v1"
    artifact_kind: Literal["scenario_instance"] = "scenario_instance"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("sci"))


class ScenarioSeriesArtifact(ArtifactDocument[ScenarioSeriesPayload]):
    schema_version: Literal["planguard.scenario-series.v1"] = "planguard.scenario-series.v1"
    artifact_kind: Literal["scenario_series"] = "scenario_series"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("scs"))


class ScenarioPhaseReceiptArtifact(ArtifactDocument[ScenarioPhaseReceiptPayload]):
    schema_version: Literal["planguard.scenario-phase-receipt.v1"] = "planguard.scenario-phase-receipt.v1"
    artifact_kind: Literal["scenario_phase_receipt"] = "scenario_phase_receipt"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("spr"))


class ScenarioRunArtifact(ArtifactDocument[ScenarioRunPayload]):
    schema_version: Literal["planguard.scenario-run.v1"] = "planguard.scenario-run.v1"
    artifact_kind: Literal["scenario_run"] = "scenario_run"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("scrun"))


class DatasetManifestArtifact(ArtifactDocument[DatasetManifestPayload]):
    schema_version: Literal["planguard.dataset-manifest.v1"] = "planguard.dataset-manifest.v1"
    artifact_kind: Literal["dataset_manifest"] = "dataset_manifest"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("dset"))


class MutationDefinitionArtifact(ArtifactDocument[MutationDefinitionPayload]):
    schema_version: Literal["planguard.mutation-definition.v1"] = "planguard.mutation-definition.v1"
    artifact_kind: Literal["mutation_definition"] = "mutation_definition"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("mut"))

class PlanObservationArtifact(ArtifactDocument[PlanObservationPayload]):
    schema_version: Literal["planguard.plan-observation.v1"] = "planguard.plan-observation.v1"
    artifact_kind: Literal["plan_observation"] = "plan_observation"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("plan"))


class PlanCollectionReceiptArtifact(ArtifactDocument[PlanCollectionReceiptPayload]):
    schema_version: Literal["planguard.plan-collection-receipt.v1"] = "planguard.plan-collection-receipt.v1"
    artifact_kind: Literal["plan_collection_receipt"] = "plan_collection_receipt"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("plrc"))


class ComparisonReportArtifact(ArtifactDocument[ComparisonReportPayload]):
    schema_version: Literal["planguard.comparison-report.v1"] = "planguard.comparison-report.v1"
    artifact_kind: Literal["comparison_report"] = "comparison_report"
    artifact_id: str = Field(default_factory=lambda: new_artifact_id("cmp"))


AnyArtifact: TypeAlias = Annotated[
    RunManifestArtifact
    | EnvironmentProfileArtifact
    | CapturePolicyArtifact
    | CapabilityGapArtifact
    | QueryExecutionArtifact
    | QueryTemplateArtifact
    | FamilySchemeArtifact
    | ObservedQueryFamilyArtifact
    | EvidenceArtifact
    | FindingArtifact
    | DetectorReceiptArtifact
    | BudgetPolicyArtifact
    | BudgetEvaluationArtifact
    | AnalysisSummaryArtifact
    | WorkloadGraphArtifact
    | WorkloadMotifArtifact
    | WorkloadEpisodeArtifact
    | ScenarioTemplateArtifact
    | ScenarioBindingArtifact
    | ScenarioInstanceArtifact
    | ScenarioSeriesArtifact
    | ScenarioPhaseReceiptArtifact
    | ScenarioRunArtifact
    | DatasetManifestArtifact
    | MutationDefinitionArtifact
    | PlanObservationArtifact
    | PlanCollectionReceiptArtifact
    | ComparisonReportArtifact,
    Field(discriminator="artifact_kind"),
]

ANY_ARTIFACT_ADAPTER = TypeAdapter(AnyArtifact)

ARTIFACT_MODELS: tuple[type[ArtifactDocument[Any]], ...] = (
    RunManifestArtifact,
    EnvironmentProfileArtifact,
    CapturePolicyArtifact,
    CapabilityGapArtifact,
    QueryExecutionArtifact,
    QueryTemplateArtifact,
    FamilySchemeArtifact,
    ObservedQueryFamilyArtifact,
    EvidenceArtifact,
    FindingArtifact,
    DetectorReceiptArtifact,
    BudgetPolicyArtifact,
    BudgetEvaluationArtifact,
    AnalysisSummaryArtifact,
    WorkloadGraphArtifact,
    WorkloadMotifArtifact,
    WorkloadEpisodeArtifact,
    ScenarioTemplateArtifact,
    ScenarioBindingArtifact,
    ScenarioInstanceArtifact,
    ScenarioSeriesArtifact,
    ScenarioPhaseReceiptArtifact,
    ScenarioRunArtifact,
    DatasetManifestArtifact,
    MutationDefinitionArtifact,
    PlanObservationArtifact,
    PlanCollectionReceiptArtifact,
    ComparisonReportArtifact,
)

SelectorExpression.model_rebuild()
