"""Explainable absolute policy evaluation for captured analyses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from planguard.analysis.engine import AnalysisBundle
from planguard.artifacts.models import (
    ArtifactReference,
    BudgetEvaluationArtifact,
    BudgetEvaluationPayload,
    BudgetPolicyArtifact,
    BudgetPolicyPayload,
    BudgetRule,
    EvaluationStatus,
    ProducerIdentity,
    Provenance,
    RuleEvaluation,
)
from planguard.policy.selectors import field_value, matches
from planguard.time import utc_now


@dataclass(frozen=True, slots=True)
class QueryPolicy:
    max_queries: int | None = None
    max_total_database_ms: float | None = None
    max_family_executions: int | None = None
    forbid_findings: frozenset[str] = frozenset()

    def to_payload(self, *, policy_key: str = "inline-query-policy.v1") -> BudgetPolicyPayload:
        rules: list[BudgetRule] = []
        if self.max_queries is not None:
            rules.append(
                BudgetRule(
                    rule_key="max-query-count",
                    subject_kind="run",
                    metric="query_count",
                    operator="less_or_equal",
                    threshold=self.max_queries,
                )
            )
        if self.max_total_database_ms is not None:
            rules.append(
                BudgetRule(
                    rule_key="max-total-database-ms",
                    subject_kind="run",
                    metric="total_database_time_ms",
                    operator="less_or_equal",
                    threshold=self.max_total_database_ms,
                )
            )
        if self.max_family_executions is not None:
            rules.append(
                BudgetRule(
                    rule_key="max-family-executions",
                    subject_kind="family",
                    metric="payload.aggregates.execution_count",
                    operator="less_or_equal",
                    threshold=self.max_family_executions,
                )
            )
        for detector_key in sorted(self.forbid_findings):
            from planguard.artifacts.models import SelectorExpression, SelectorOperator

            rules.append(
                BudgetRule(
                    rule_key=f"forbid-{detector_key}",
                    subject_kind="finding",
                    selector=SelectorExpression(
                        operator=SelectorOperator.EQUALS,
                        field="payload.detector_key",
                        value=detector_key,
                    ),
                    operator="no_matches",
                )
            )
        return BudgetPolicyPayload(
            policy_key=policy_key,
            title="Inline PlanGuard query policy",
            rules=tuple(rules),
        )


def _subjects(bundle: AnalysisBundle, kind: str) -> tuple[Any, ...]:
    if kind == "run":
        return (bundle.summary.payload,)
    if kind == "family":
        return bundle.families
    if kind == "finding":
        return bundle.findings
    if kind == "detector_receipt":
        return bundle.detector_receipts
    return ()


def _evaluate_comparison(actual: Any, operator: str, threshold: Any) -> bool:
    if operator == "less_or_equal":
        return actual <= threshold
    if operator == "less_than":
        return actual < threshold
    if operator == "greater_or_equal":
        return actual >= threshold
    if operator == "greater_than":
        return actual > threshold
    if operator == "equals":
        return actual == threshold
    raise ValueError(f"Unsupported comparison operator: {operator}")


def evaluate_policy(
    bundle: AnalysisBundle,
    policy: BudgetPolicyArtifact,
    *,
    producer: ProducerIdentity,
) -> BudgetEvaluationArtifact:
    evaluations: list[RuleEvaluation] = []
    overall = EvaluationStatus.PASSED
    for rule in policy.payload.rules:
        candidates = tuple(item for item in _subjects(bundle, rule.subject_kind) if matches(rule.selector, item))
        refs: tuple[ArtifactReference, ...] = tuple(
            item.reference() for item in candidates if hasattr(item, "reference")
        )
        status = EvaluationStatus.PASSED
        measured: Any = None
        try:
            if rule.operator == "no_matches":
                measured = len(candidates)
                passed = measured == 0
            elif rule.operator == "has_matches":
                measured = len(candidates)
                passed = measured > 0
            elif rule.subject_kind == "run":
                measured = field_value(candidates[0], rule.metric or "") if candidates else None
                passed = measured is not None and _evaluate_comparison(
                    measured, rule.operator, rule.threshold
                )
            else:
                values = [field_value(item, rule.metric or "") for item in candidates]
                values = [value for value in values if value.__class__.__name__ != "Missing"]
                measured = max(values) if values else None
                passed = measured is not None and _evaluate_comparison(
                    measured, rule.operator, rule.threshold
                )
            if not passed:
                status = (
                    EvaluationStatus.WARNED
                    if rule.disposition == "warn"
                    else EvaluationStatus.FAILED
                )
        except (TypeError, ValueError, IndexError) as exc:
            status = EvaluationStatus.NOT_EVALUATED
            message = f"Rule could not be evaluated: {exc}"
        else:
            message = rule.message or (
                f"Rule {rule.rule_key} passed."
                if status == EvaluationStatus.PASSED
                else f"Rule {rule.rule_key} observed {measured!r} against {rule.threshold!r}."
            )
        if status == EvaluationStatus.FAILED:
            overall = EvaluationStatus.FAILED
        elif status == EvaluationStatus.WARNED and overall == EvaluationStatus.PASSED:
            overall = EvaluationStatus.WARNED
        elif status == EvaluationStatus.NOT_EVALUATED and overall == EvaluationStatus.PASSED:
            overall = EvaluationStatus.NOT_EVALUATED
        evaluations.append(
            RuleEvaluation(
                rule_key=rule.rule_key,
                status=status,
                measured_value=measured,
                threshold=rule.threshold,
                matched_subject_refs=refs,
                message=message,
            )
        )
    return BudgetEvaluationArtifact(
        producer=producer,
        provenance=Provenance(
            input_refs=(bundle.summary.reference(), policy.reference()),
            configuration_ref=policy.reference(),
            derivation_key="budget-policy-evaluate.v1",
        ),
        payload=BudgetEvaluationPayload(
            run_id=bundle.run_id,
            policy_ref=policy.reference(),
            status=overall,
            rule_evaluations=tuple(evaluations),
            evaluated_at=utc_now(),
        ),
    ).seal()
