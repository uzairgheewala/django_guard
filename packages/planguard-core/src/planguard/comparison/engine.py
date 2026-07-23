"""Comparability-first analysis of PlanGuard baseline and candidate runs."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from planguard.analysis.engine import AnalysisBundle
from planguard.artifacts.models import (
    ArtifactReference, BudgetPolicyArtifact, ComparabilityState, ComparisonReportArtifact,
    ComparisonReportPayload, ComparisonStatus, DimensionAssessment, EvaluationStatus,
    FamilyChange, FindingArtifact, FindingChange, MetricDelta, PlanChange,
    PlanObservationArtifact, ProducerIdentity, Provenance, RelativeRuleEvaluation,
    RunManifestArtifact,
)
from planguard.policy.selectors import field_value, MISSING


def _relative(baseline: float | int | None, candidate: float | int | None) -> float | None:
    if baseline is None or candidate is None or baseline == 0:
        return None
    return (candidate - baseline) / baseline


def _metric(key: str, baseline: float | int | None, candidate: float | int | None, *, lower_is_better: bool = True, unit: str | None = None, validity: str = "valid") -> MetricDelta:
    absolute = candidate - baseline if baseline is not None and candidate is not None else None
    rel = _relative(baseline, candidate)
    if absolute is None:
        direction = "unknown"
    elif absolute == 0:
        direction = "unchanged"
    elif (absolute < 0) == lower_is_better:
        direction = "improved"
    else:
        direction = "regressed"
    return MetricDelta(metric_key=key, baseline=baseline, candidate=candidate, absolute_delta=absolute, relative_delta=rel, unit=unit, direction=direction, validity=validity)  # type: ignore[arg-type]


def _scenario_value(manifest: RunManifestArtifact, loader, field: str) -> Any:
    ref = manifest.payload.scenario_instance_ref
    if ref is None:
        return None
    try:
        instance = loader(ref.artifact_id)
    except Exception:
        return None
    value = field_value(instance.payload, field)
    return None if value is MISSING else value


def assess_comparability(baseline: RunManifestArtifact, candidate: RunManifestArtifact, *, loader) -> tuple[ComparisonStatus, tuple[DimensionAssessment, ...]]:
    dimensions: list[DimensionAssessment] = []

    def add(key: str, a: Any, b: Any, *, controlled: bool = False, affects: tuple[str, ...] = ("timing",)):
        if a is None or b is None:
            state = ComparabilityState.UNKNOWN
            explanation = f"{key} could not be established for both runs."
        elif a == b:
            state = ComparabilityState.IDENTICAL
            explanation = f"{key} is identical."
        elif controlled:
            state = ComparabilityState.CONTROLLED_CHANGE
            explanation = f"{key} differs as a declared controlled change."
        else:
            state = ComparabilityState.CONFOUNDING_CHANGE
            explanation = f"{key} differs and may confound the affected comparison layers."
        dimensions.append(DimensionAssessment(dimension_key=key, state=state, baseline_value=a, candidate_value=b, explanation=explanation, affects=affects))  # type: ignore[arg-type]

    add("scenario.template", _scenario_value(baseline, loader, "template_ref.content_hash"), _scenario_value(candidate, loader, "template_ref.content_hash"), affects=("correctness", "structure", "plans", "resources", "timing"))
    add("scenario.binding", _scenario_value(baseline, loader, "binding_ref.content_hash"), _scenario_value(candidate, loader, "binding_ref.content_hash"), affects=("correctness", "structure", "plans", "resources", "timing"))
    add("scenario.parameters", _scenario_value(baseline, loader, "parameter_bindings"), _scenario_value(candidate, loader, "parameter_bindings"), affects=("correctness", "structure", "plans", "resources", "timing"))
    add("scenario.seed", _scenario_value(baseline, loader, "seed"), _scenario_value(candidate, loader, "seed"), affects=("correctness", "structure", "plans", "resources", "timing"))
    add("implementation.variant", _scenario_value(baseline, loader, "variant_key"), _scenario_value(candidate, loader, "variant_key"), controlled=True, affects=("structure", "plans", "resources", "timing"))
    def referenced_payload(ref):
        if ref is None:
            return None
        try:
            return loader(ref.artifact_id).payload.model_dump(mode="json", exclude_none=False)
        except Exception:
            return None
    add("environment.profile", referenced_payload(baseline.payload.environment_ref), referenced_payload(candidate.payload.environment_ref), affects=("plans", "resources", "timing"))
    add("capture.policy", referenced_payload(baseline.payload.capture_policy_ref), referenced_payload(candidate.payload.capture_policy_ref), affects=("structure", "resources", "timing"))

    states = {item.state for item in dimensions}
    structural_confounds = any(item.state == ComparabilityState.CONFOUNDING_CHANGE and any(layer in item.affects for layer in ("correctness", "structure")) for item in dimensions)
    timing_confounds = any(item.state in {ComparabilityState.CONFOUNDING_CHANGE, ComparabilityState.UNKNOWN} and "timing" in item.affects for item in dimensions)
    if structural_confounds:
        status = ComparisonStatus.INVALID
    elif timing_confounds:
        status = ComparisonStatus.DEGRADED
    elif ComparabilityState.CONTROLLED_CHANGE in states:
        status = ComparisonStatus.VALID_WITH_CONTROLLED_CHANGES
    else:
        status = ComparisonStatus.VALID
    return status, tuple(dimensions)


def _families_by_shape(bundle: AnalysisBundle) -> dict[str, list[Any]]:
    template_by_id = {item.artifact_id: item for item in bundle.templates}
    result: dict[str, list[Any]] = defaultdict(list)
    for family in bundle.families:
        if family.payload.family_scheme_key != "shape-origin.v1":
            continue
        template = template_by_id.get(family.payload.query_template_ref.artifact_id)
        if template:
            result[template.payload.structural_shape_fingerprint].append(family)
    return result


def compare_families(baseline: AnalysisBundle, candidate: AnalysisBundle) -> tuple[FamilyChange, ...]:
    left = _families_by_shape(baseline); right = _families_by_shape(candidate)
    changes: list[FamilyChange] = []
    for shape in sorted(set(left) | set(right)):
        a, b = left.get(shape, []), right.get(shape, [])
        if not a:
            kind = "added"
        elif not b:
            kind = "removed"
        elif len(a) < len(b):
            kind = "split"
        elif len(a) > len(b):
            kind = "merged"
        else:
            a_count = sum(x.payload.aggregates.execution_count for x in a)
            b_count = sum(x.payload.aggregates.execution_count for x in b)
            kind = "unchanged" if a_count == b_count else "changed"
        a_count = sum(x.payload.aggregates.execution_count for x in a)
        b_count = sum(x.payload.aggregates.execution_count for x in b)
        a_ms = sum(x.payload.aggregates.total_duration_ms for x in a)
        b_ms = sum(x.payload.aggregates.total_duration_ms for x in b)
        changes.append(FamilyChange(change_kind=kind, baseline_family_refs=tuple(x.reference() for x in a), candidate_family_refs=tuple(x.reference() for x in b), structural_shape_fingerprint=shape, deltas=(_metric("execution_count", a_count, b_count), _metric("database_time_ms", a_ms, b_ms, unit="ms")), explanation=f"Structural query family {shape} is {kind} in the candidate."))  # type: ignore[arg-type]
    return tuple(changes)


def _finding_groups(findings: Iterable[FindingArtifact]) -> dict[str, list[FindingArtifact]]:
    result: dict[str, list[FindingArtifact]] = defaultdict(list)
    for finding in findings: result[finding.payload.mechanism_key].append(finding)
    return result


def compare_findings(baseline: AnalysisBundle, candidate: AnalysisBundle) -> tuple[FindingChange, ...]:
    left, right = _finding_groups(baseline.findings), _finding_groups(candidate.findings)
    output: list[FindingChange] = []
    for mechanism in sorted(set(left) | set(right)):
        a, b = left.get(mechanism, []), right.get(mechanism, [])
        if a and not b: kind = "resolved"
        elif b and not a: kind = "introduced"
        elif len(a) == len(b): kind = "unchanged"
        else: kind = "changed"
        output.append(FindingChange(change_kind=kind, mechanism_key=mechanism, baseline_finding_refs=tuple(x.reference() for x in a), candidate_finding_refs=tuple(x.reference() for x in b), explanation=f"Finding mechanism {mechanism} is {kind}."))  # type: ignore[arg-type]
    return tuple(output)


def _plans_by_shape(plans: Iterable[PlanObservationArtifact], bundle: AnalysisBundle) -> dict[str, list[PlanObservationArtifact]]:
    fam_by_id = {family.artifact_id: family for family in bundle.families}
    tpl_by_id = {tpl.artifact_id: tpl for tpl in bundle.templates}
    result: dict[str, list[PlanObservationArtifact]] = defaultdict(list)
    for plan in plans:
        family = fam_by_id.get(plan.payload.query_family_ref.artifact_id)
        template = tpl_by_id.get(family.payload.query_template_ref.artifact_id) if family else None
        if template: result[template.payload.structural_shape_fingerprint].append(plan)
    return result


def compare_plans(baseline_plans: Iterable[PlanObservationArtifact], candidate_plans: Iterable[PlanObservationArtifact], baseline: AnalysisBundle, candidate: AnalysisBundle) -> tuple[PlanChange, ...]:
    left, right = _plans_by_shape(baseline_plans, baseline), _plans_by_shape(candidate_plans, candidate)
    output: list[PlanChange] = []
    for shape in sorted(set(left) | set(right)):
        a = left.get(shape, []); b = right.get(shape, [])
        pa = a[0] if a else None; pb = b[0] if b else None
        if pa is None: kind = "added"
        elif pb is None: kind = "removed"
        elif pa.payload.features.plan_shape_fingerprint == pb.payload.features.plan_shape_fingerprint: kind = "unchanged"
        else: kind = "changed"
        transitions: list[str] = []
        if pa and pb:
            relations = set(pa.payload.features.relation_access) | set(pb.payload.features.relation_access)
            for relation in sorted(relations):
                before = pa.payload.features.relation_access.get(relation, ())
                after = pb.payload.features.relation_access.get(relation, ())
                if before != after: transitions.append(f"{relation}: {', '.join(before) or 'none'} → {', '.join(after) or 'none'}")
            if set(pa.payload.features.index_names) != set(pb.payload.features.index_names): transitions.append(f"indexes: {', '.join(pa.payload.features.index_names) or 'none'} → {', '.join(pb.payload.features.index_names) or 'none'}")
        deltas = () if not (pa and pb) else (
            _metric("shared_read_blocks", pa.payload.features.shared_read_blocks, pb.payload.features.shared_read_blocks, unit="blocks"),
            _metric("temporary_io_blocks", pa.payload.features.temporary_io_blocks, pb.payload.features.temporary_io_blocks, unit="blocks"),
            _metric("execution_time_ms", pa.payload.features.execution_time_ms, pb.payload.features.execution_time_ms, unit="ms", validity="valid" if pa.payload.collection.analyzed and pb.payload.collection.analyzed else "not_available"),
        )
        severity = "medium" if kind == "changed" and transitions else "info"
        output.append(PlanChange(change_kind=kind, baseline_plan_ref=pa.reference() if pa else None, candidate_plan_ref=pb.reference() if pb else None, query_shape_fingerprint=shape, transitions=tuple(transitions), deltas=deltas, severity=severity, explanation=f"Plan for query shape {shape} is {kind}."))  # type: ignore[arg-type]
    return tuple(output)


def evaluate_relative_policy(report_payload: ComparisonReportPayload, policy: BudgetPolicyArtifact | None) -> tuple[RelativeRuleEvaluation, ...]:
    if policy is None: return ()
    metrics = {item.metric_key: item for item in report_payload.metric_deltas}
    output: list[RelativeRuleEvaluation] = []
    for rule in policy.payload.rules:
        if rule.subject_kind != "comparison": continue
        metric_key = str(rule.metric or "")
        relative_metric = metric_key.endswith(".relative")
        base_key = metric_key[:-9] if relative_metric else metric_key
        item = metrics.get(base_key)
        if item is None:
            output.append(RelativeRuleEvaluation(rule_key=rule.rule_key, status=EvaluationStatus.NOT_EVALUATED, metric_key=rule.metric, threshold=rule.threshold, message="Comparison metric is unavailable.")); continue
        measured = item.relative_delta if relative_metric else item.absolute_delta
        try:
            if rule.operator == "less_or_equal": passed = measured is not None and measured <= rule.threshold
            elif rule.operator == "less_than": passed = measured is not None and measured < rule.threshold
            elif rule.operator == "greater_or_equal": passed = measured is not None and measured >= rule.threshold
            elif rule.operator == "greater_than": passed = measured is not None and measured > rule.threshold
            elif rule.operator == "equals": passed = measured == rule.threshold
            else: raise ValueError("relative policies require scalar comparison operators")
            status = EvaluationStatus.PASSED if passed else (EvaluationStatus.WARNED if rule.disposition == "warn" else EvaluationStatus.FAILED)
            message = rule.message or f"Observed {measured!r} against {rule.threshold!r}."
        except Exception as exc:
            status = EvaluationStatus.NOT_EVALUATED; message = f"Rule could not be evaluated: {exc}"
        output.append(RelativeRuleEvaluation(rule_key=rule.rule_key, status=status, metric_key=rule.metric, measured_value=measured, threshold=rule.threshold, message=message))
    return tuple(output)


def compare_runs(*, baseline_manifest: RunManifestArtifact, candidate_manifest: RunManifestArtifact, baseline: AnalysisBundle, candidate: AnalysisBundle, loader, producer: ProducerIdentity, baseline_plans: Iterable[PlanObservationArtifact] = (), candidate_plans: Iterable[PlanObservationArtifact] = (), relative_policy: BudgetPolicyArtifact | None = None) -> ComparisonReportArtifact:
    status, dimensions = assess_comparability(baseline_manifest, candidate_manifest, loader=loader)
    timing_validity = "valid" if status in {ComparisonStatus.VALID, ComparisonStatus.VALID_WITH_CONTROLLED_CHANGES} else "advisory"
    metrics = (
        _metric("query_count", baseline.summary.payload.query_count, candidate.summary.payload.query_count),
        _metric("query_template_count", baseline.summary.payload.query_template_count, candidate.summary.payload.query_template_count),
        _metric("family_count", len(baseline.families), len(candidate.families)),
        _metric("finding_count", len(baseline.findings), len(candidate.findings)),
        _metric("total_database_time_ms", baseline.summary.payload.total_database_time_ms, candidate.summary.payload.total_database_time_ms, unit="ms", validity=timing_validity),
    )
    family_changes = compare_families(baseline, candidate)
    plan_changes = compare_plans(baseline_plans, candidate_plans, baseline, candidate)
    finding_changes = compare_findings(baseline, candidate)
    payload = ComparisonReportPayload(
        baseline_run_ref=baseline_manifest.reference(), candidate_run_ref=candidate_manifest.reference(), status=status,
        dimensions=dimensions, changed_dimensions=tuple(item.dimension_key for item in dimensions if item.state != ComparabilityState.IDENTICAL),
        metric_deltas=metrics, family_changes=family_changes, plan_changes=plan_changes, finding_changes=finding_changes,
        relative_policy_ref=relative_policy.reference() if relative_policy else None,
        narrative=_narrative(status, metrics, family_changes, plan_changes, finding_changes),
        limitations=tuple(["Timing deltas are advisory because environment comparability is incomplete."] if timing_validity != "valid" else ()),
    )
    payload = payload.model_copy(update={"relative_rule_evaluations": evaluate_relative_policy(payload, relative_policy)})
    refs = [baseline_manifest.reference(), candidate_manifest.reference(), baseline.summary.reference(), candidate.summary.reference()]
    refs.extend(plan.reference() for plan in (*tuple(baseline_plans), *tuple(candidate_plans)))
    if relative_policy: refs.append(relative_policy.reference())
    return ComparisonReportArtifact(producer=producer, provenance=Provenance(input_refs=tuple(refs), configuration_ref=relative_policy.reference() if relative_policy else None, derivation_key="run-comparison.v1"), payload=payload).seal()


def _narrative(status, metrics, family_changes, plan_changes, finding_changes) -> tuple[str, ...]:
    by_key = {item.metric_key: item for item in metrics}
    statements = [f"Comparison status is {status}." ]
    query = by_key["query_count"]
    if query.absolute_delta is not None:
        statements.append(f"Query count changed from {query.baseline} to {query.candidate} ({query.direction}).")
    removed = [item for item in family_changes if item.change_kind == "removed"]
    introduced = [item for item in finding_changes if item.change_kind == "introduced"]
    resolved = [item for item in finding_changes if item.change_kind == "resolved"]
    changed_plans = [item for item in plan_changes if item.change_kind == "changed"]
    if removed: statements.append(f"{len(removed)} structural query family or families were removed.")
    if resolved: statements.append(f"{len(resolved)} finding mechanism or mechanisms were resolved.")
    if introduced: statements.append(f"{len(introduced)} finding mechanism or mechanisms were introduced.")
    if changed_plans: statements.append(f"{len(changed_plans)} matched plan or plans changed topology.")
    return tuple(statements)
