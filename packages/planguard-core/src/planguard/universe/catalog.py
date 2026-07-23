"""Built-in universe profiles derived from generic scenario contracts."""

from __future__ import annotations

from planguard.artifacts.models import (
    CoverageStrategyDefinition,
    ParameterDomain,
    ParameterDomainKind,
    ParameterPartition,
    MutationDefinitionArtifact,
    ProducerIdentity,
    Provenance,
    ScenarioBindingArtifact,
    ScenarioTemplateArtifact,
    UniverseAxis,
    UniverseConstraint,
    UniverseConstraintKind,
    UniversePredicate,
    UniverseProfileArtifact,
    UniverseProfilePayload,
)
from planguard.canonical import canonical_json_bytes
from planguard.ids import content_derived_id
from planguard.time import semantic_epoch


def build_django_postgres_universe(
    *,
    templates: tuple[ScenarioTemplateArtifact, ...],
    bindings: tuple[ScenarioBindingArtifact, ...],
    mutations: tuple[MutationDefinitionArtifact, ...] = (),
    producer: ProducerIdentity,
) -> UniverseProfileArtifact:
    """Create the declared Milestone F universe over the available scenario catalog."""

    template_keys = tuple(sorted(item.payload.template_key for item in templates))
    binding_keys = tuple(sorted(item.payload.binding_key for item in bindings))
    mutation_values = (
        "none",
        *(sorted(item.payload.mutation_key for item in mutations) if mutations else (
            "remove-eager-loading.v1",
            "force-per-row-write.v1",
            "remove-composite-tenant-index.v1",
            "increase-tenant-skew.v1",
            "expand-object-hydration.v1",
            "extend-transaction-scope.v1",
            "stale-statistics.v1",
            "increase-relation-fanout.v1",
        )),
    )
    axes = (
        UniverseAxis(
            axis_key="template_key",
            title="Workload topology",
            domain=ParameterDomain(kind=ParameterDomainKind.FINITE, values=template_keys),
            source_kind="registry",
            source_key="scenario.templates",
            risk_weight=2.0,
        ),
        UniverseAxis(
            axis_key="binding_key",
            title="Application binding",
            domain=ParameterDomain(kind=ParameterDomainKind.FINITE, values=binding_keys),
            source_kind="registry",
            source_key="scenario.bindings",
        ),
        UniverseAxis(
            axis_key="variant_key",
            title="Implementation variant",
            domain=ParameterDomain(kind=ParameterDomainKind.FINITE, values=("naive", "optimized"), default="naive"),
            source_kind="scenario_parameter",
            source_key="variant_key",
        ),
        UniverseAxis(
            axis_key="scale_profile",
            title="Logical data scale",
            domain=ParameterDomain(kind=ParameterDomainKind.FINITE, values=("tiny", "small", "medium", "large"), default="tiny"),
            source_key="scale_profile",
            risk_weight=1.5,
        ),
        UniverseAxis(
            axis_key="tenant_skew",
            title="Tenant distribution",
            domain=ParameterDomain(kind=ParameterDomainKind.FINITE, values=("uniform", "dominant", "zipf"), default="uniform"),
            source_key="tenant_skew",
            risk_weight=1.5,
        ),
        UniverseAxis(
            axis_key="parent_count",
            title="Parent cardinality",
            domain=ParameterDomain(
                kind=ParameterDomainKind.PARTITIONED,
                partitions=(
                    ParameterPartition(key="empty", minimum=0, maximum=0, representative_values=(0,)),
                    ParameterPartition(key="singleton", minimum=1, maximum=1, representative_values=(1,)),
                    ParameterPartition(key="small", minimum=2, maximum=10, representative_values=(5,)),
                    ParameterPartition(key="medium", minimum=11, maximum=100, representative_values=(50,)),
                    ParameterPartition(key="large", minimum=101, maximum=1000, representative_values=(250,)),
                ),
                default=8,
            ),
            source_key="parent_count",
            risk_weight=2.0,
        ),
        UniverseAxis(
            axis_key="relation_fanout",
            title="Relation fan-out",
            domain=ParameterDomain(
                kind=ParameterDomainKind.PARTITIONED,
                partitions=(
                    ParameterPartition(key="none", minimum=0, maximum=0, representative_values=(0,)),
                    ParameterPartition(key="one", minimum=1, maximum=1, representative_values=(1,)),
                    ParameterPartition(key="bounded", minimum=2, maximum=10, representative_values=(5,)),
                    ParameterPartition(key="high", minimum=11, maximum=100, representative_values=(25,)),
                ),
                default=5,
            ),
            source_key="relation_fanout",
            risk_weight=1.5,
        ),
        UniverseAxis(
            axis_key="transaction_scope",
            title="Transaction scope",
            domain=ParameterDomain(kind=ParameterDomainKind.FINITE, values=("autocommit", "short_atomic", "long_atomic"), default="autocommit"),
            source_key="transaction_scope",
        ),
        UniverseAxis(
            axis_key="mutation_key",
            title="Controlled perturbation",
            domain=ParameterDomain(kind=ParameterDomainKind.FINITE, values=mutation_values, default="none"),
            source_kind="registry",
            source_key="scenario.mutations",
            risk_weight=1.5,
        ),
    )
    constraints = (
        UniverseConstraint(
            constraint_key="binding-matches-template",
            kind=UniverseConstraintKind.APPLICABILITY,
            explanation="A binding must reference the selected scenario template.",
        ),
        UniverseConstraint(
            constraint_key="fanout-needs-relation-topology",
            kind=UniverseConstraintKind.EXCLUSION,
            when=(UniversePredicate(field="relation_fanout", operator="not_equals", value="none"),),
            require=(UniversePredicate(field="template_key", operator="in", value=("relation-access-fanout.v1", "nested-relation-fanout.v1")),),
            explanation="Nontrivial relation fan-out is only meaningful for relation traversal templates.",
        ),
        UniverseConstraint(
            constraint_key="long-transaction-mutation-needs-transactional-workload",
            kind=UniverseConstraintKind.IMPLICATION,
            when=(UniversePredicate(field="mutation_key", operator="equals", value="extend-transaction-scope.v1"),),
            require=(UniversePredicate(field="transaction_scope", operator="equals", value="long_atomic"),),
            explanation="The transaction-scope mutation implies a long atomic transaction.",
        ),
        UniverseConstraint(
            constraint_key="write-mutation-needs-write-topology",
            kind=UniverseConstraintKind.EXCLUSION,
            when=(UniversePredicate(field="mutation_key", operator="equals", value="force-per-row-write.v1"),),
            require=(UniversePredicate(field="template_key", operator="in", value=("per-item-check-write.v1", "per-item-update.v1")),),
            explanation="Per-row write perturbations require a write-oriented scenario.",
        ),
        UniverseConstraint(
            constraint_key="tenant-index-mutation-needs-tenant-query",
            kind=UniverseConstraintKind.EXCLUSION,
            when=(UniversePredicate(field="mutation_key", operator="equals", value="remove-composite-tenant-index.v1"),),
            require=(UniversePredicate(field="template_key", operator="in", value=("tenant-skew-sensitivity.v1", "aggregate-report.v1")),),
            explanation="Tenant index perturbations require a tenant-scoped workload.",
        ),
    )
    strategies = (
        CoverageStrategyDefinition(strategy_key="axis-partitions.v1", kind="partition", dimensions=tuple(axis.axis_key for axis in axes), priority=10),
        CoverageStrategyDefinition(strategy_key="boundary-values.v1", kind="boundary", dimensions=("parent_count", "relation_fanout"), priority=20),
        CoverageStrategyDefinition(strategy_key="high-risk-pairwise.v1", kind="pairwise", dimensions=("template_key", "variant_key", "scale_profile", "tenant_skew", "mutation_key"), priority=30),
        CoverageStrategyDefinition(strategy_key="motif-coverage.v1", kind="motif", dimensions=("template_key",), priority=40),
        CoverageStrategyDefinition(strategy_key="mutation-coverage.v1", kind="mutation", dimensions=("mutation_key",), priority=50),
        CoverageStrategyDefinition(strategy_key="metamorphic-scale.v1", kind="metamorphic", dimensions=("parent_count", "scale_profile"), priority=60),
    )
    payload = UniverseProfilePayload(
        universe_key="django-postgres-core.v1",
        title="Django/PostgreSQL workload behavior",
        description="A constrained universe of generic workload topologies, application bindings, data regimes, implementation variants, and controlled perturbations.",
        target_capabilities=(
            "scenario.template",
            "scenario.binding",
            "scenario.execution",
            "query.capture.django",
            "query.family",
            "workload.graph",
            "workload.motif",
            "plan.postgresql",
            "comparison.semantic",
        ),
        axes=axes,
        constraints=constraints,
        strategies=strategies,
        template_refs=tuple(item.reference() for item in templates),
        binding_refs=tuple(item.reference() for item in bindings),
        mutation_refs=tuple(item.reference() for item in mutations),
        tags=("builtin", "django", "postgresql", "milestone-f"),
    )
    artifact_id = content_derived_id(
        "univ",
        canonical_json_bytes({"payload": payload, "producer": producer.model_dump(mode="python")}),
        length=32,
    )
    return UniverseProfileArtifact(
        created_at=semantic_epoch(),
        artifact_id=artifact_id,
        producer=producer,
        provenance=Provenance(
            input_refs=(*payload.template_refs, *payload.binding_refs, *payload.mutation_refs),
            derivation_key="builtin-universe-profile.v1",
        ),
        payload=payload,
    ).seal()
