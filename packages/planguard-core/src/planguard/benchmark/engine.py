"""Deterministic benchmark execution and robust descriptive statistics.

The engine intentionally avoids claiming formal algorithmic complexity or causal
improvement from a single timing. It records every sample, exclusions, environment
limitations, and a conservative observed-scaling classification.
"""

from __future__ import annotations

import math
import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, wait
from threading import Barrier
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from itertools import product
from typing import Any

from planguard.artifacts.models import (
    ArtifactReference,
    BenchmarkProtocolArtifact,
    BenchmarkSample,
    BenchmarkStatus,
    ExperimentSeriesArtifact,
    ExperimentSeriesPayload,
    MetricDistribution,
    ProducerIdentity,
    Provenance,
    ScalingAssessment,
    ScalingClassification,
)
from planguard.ids import new_artifact_id
from planguard.time import utc_now


@dataclass(frozen=True, slots=True)
class BenchmarkMeasurement:
    metrics: Mapping[str, float]
    scenario_run_ref: ArtifactReference | None = None
    analysis_run_ref: ArtifactReference | None = None
    valid: bool = True
    excluded_reason: str | None = None


def _percentile(sorted_values: Sequence[float], fraction: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = (len(sorted_values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    weight = position - lower
    return float(sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight)


def _included_values(values: Sequence[float], policy: str) -> tuple[list[float], int]:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if len(finite) < 4 or policy == "none":
        return finite, len(values) - len(finite)
    ordered = sorted(finite)
    if policy == "iqr":
        q1 = _percentile(ordered, 0.25)
        q3 = _percentile(ordered, 0.75)
        assert q1 is not None and q3 is not None
        iqr = q3 - q1
        low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    else:
        median = statistics.median(ordered)
        deviations = [abs(value - median) for value in ordered]
        mad = statistics.median(deviations)
        if mad == 0:
            return finite, len(values) - len(finite)
        low, high = median - 3.5 * mad, median + 3.5 * mad
    included = [value for value in finite if low <= value <= high]
    return included, len(values) - len(included)


def summarize_metric(
    metric_key: str,
    values: Sequence[float],
    *,
    outlier_policy: str = "mad",
    confidence_level: float = 0.95,
    unit: str | None = None,
) -> MetricDistribution:
    included, excluded = _included_values(values, outlier_policy)
    if not included:
        return MetricDistribution(
            metric_key=metric_key,
            sample_count=0,
            excluded_count=excluded,
            unit=unit,
        )
    ordered = sorted(included)
    mean = statistics.fmean(ordered)
    median = statistics.median(ordered)
    std = statistics.stdev(ordered) if len(ordered) > 1 else 0.0
    mad = statistics.median(abs(value - median) for value in ordered)
    # Normal approximation is intentionally labeled descriptive rather than inferential.
    z = 1.96 if confidence_level >= 0.95 else 1.645
    margin = z * std / math.sqrt(len(ordered)) if ordered else 0.0
    return MetricDistribution(
        metric_key=metric_key,
        sample_count=len(ordered),
        excluded_count=excluded,
        minimum=min(ordered),
        maximum=max(ordered),
        mean=mean,
        median=median,
        p95=_percentile(ordered, 0.95),
        standard_deviation=std,
        median_absolute_deviation=mad,
        confidence_low=mean - margin,
        confidence_high=mean + margin,
        unit=unit,
    )


def analyze_scaling(
    *,
    metric_key: str,
    independent_dimension: str,
    points: Sequence[tuple[float, float]],
) -> ScalingAssessment:
    usable = sorted((float(x), float(y)) for x, y in points if x > 0 and y >= 0 and math.isfinite(x) and math.isfinite(y))
    if len(usable) < 3 or len({x for x, _ in usable}) < 3:
        return ScalingAssessment(
            metric_key=metric_key,
            independent_dimension=independent_dimension,
            classification=ScalingClassification.INCONCLUSIVE,
            sample_points=len(usable),
            explanation=("At least three distinct positive scale points are required.",),
        )
    xs = [math.log(x) for x, _ in usable]
    ys = [math.log(max(y, 1e-12)) for _, y in usable]
    x_mean, y_mean = statistics.fmean(xs), statistics.fmean(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True)) / denominator if denominator else 0.0
    y_hat = [y_mean + slope * (x - x_mean) for x in xs]
    ss_total = sum((y - y_mean) ** 2 for y in ys)
    ss_residual = sum((y - pred) ** 2 for y, pred in zip(ys, y_hat, strict=True))
    r2 = 1.0 - ss_residual / ss_total if ss_total else 1.0
    ratios = [usable[index + 1][1] / max(usable[index][1], 1e-12) for index in range(len(usable) - 1)]
    transition_index = max(range(len(ratios)), key=lambda index: ratios[index]) if ratios else 0
    threshold = ratios[transition_index] >= 4 and ratios[transition_index] >= 2 * statistics.median(ratios)
    if threshold:
        classification = ScalingClassification.THRESHOLD_TRANSITION
        transition_at: Any = usable[transition_index + 1][0]
    elif slope < 0.25:
        classification = ScalingClassification.APPROXIMATELY_CONSTANT
        transition_at = None
    elif slope < 0.8:
        classification = ScalingClassification.SUBLINEAR
        transition_at = None
    elif slope <= 1.25:
        classification = ScalingClassification.APPROXIMATELY_LINEAR
        transition_at = None
    else:
        classification = ScalingClassification.SUPERLINEAR
        transition_at = None
    confidence = max(0.0, min(1.0, r2))
    return ScalingAssessment(
        metric_key=metric_key,
        independent_dimension=independent_dimension,
        classification=classification,
        slope=slope,
        transition_at=transition_at,
        sample_points=len(usable),
        confidence=confidence,
        explanation=(
            f"Observed log-log slope {slope:.3f} across {len(usable)} points.",
            f"Descriptive fit R² {r2:.3f}; this is not a formal Big-O proof.",
        ),
    )


def run_concurrent_operation(
    concurrency: int,
    operation: Callable[[int], Mapping[str, float] | None],
    *,
    timeout_seconds: float = 60.0,
) -> BenchmarkMeasurement:
    """Execute one operation per worker behind a common start barrier.

    The result retains worker errors and timeouts as metrics instead of silently
    discarding them. Database-specific lock telemetry can be returned by each
    worker and is aggregated by key.
    """

    if concurrency < 1:
        raise ValueError("concurrency must be positive")
    barrier = Barrier(concurrency)
    metrics: list[Mapping[str, float]] = []
    errors: list[str] = []

    def worker(index: int):
        try:
            barrier.wait(timeout=timeout_seconds)
            result = operation(index) or {}
            return dict(result), None
        except Exception as exc:
            return {}, f"{type(exc).__name__}: {exc}"

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="planguard-benchmark") as executor:
        futures = [executor.submit(worker, index) for index in range(concurrency)]
        done, pending = wait(futures, timeout=timeout_seconds)
        for future in done:
            result, error = future.result()
            metrics.append(result)
            if error:
                errors.append(error)
        for future in pending:
            future.cancel()
    wall_time_ms = (time.perf_counter() - started) * 1000
    aggregated: dict[str, float] = {"wall_time_ms": wall_time_ms}
    for item in metrics:
        for key, value in item.items():
            aggregated[key] = aggregated.get(key, 0.0) + float(value)
    successful = max(0, concurrency - len(errors) - len(pending))
    aggregated["throughput_ops_s"] = successful / max(wall_time_ms / 1000.0, 1e-12)
    aggregated["error_count"] = float(len(errors))
    aggregated["timeout_count"] = float(len(pending))
    return BenchmarkMeasurement(
        metrics=aggregated,
        valid=not pending,
        excluded_reason=("; ".join(errors) if errors else ("Worker timeout" if pending else None)),
    )


class BenchmarkRunner:
    def __init__(self, *, producer: ProducerIdentity) -> None:
        self.producer = producer

    def run(
        self,
        protocol: BenchmarkProtocolArtifact,
        executor: Callable[[dict[str, Any], int, bool], BenchmarkMeasurement | Mapping[str, float]],
        *,
        cases: Iterable[Mapping[str, Any]] | None = None,
        independent_dimension: str | None = None,
        environment_refs: tuple[ArtifactReference, ...] = (),
        comparability_notes: tuple[str, ...] = (),
    ) -> ExperimentSeriesArtifact:
        payload = protocol.payload
        if cases is None:
            if payload.dimensions:
                keys = [dimension.dimension_key for dimension in payload.dimensions]
                values = [dimension.values for dimension in payload.dimensions]
                case_list = [dict(zip(keys, combination, strict=True)) for combination in product(*values)]
            else:
                case_list = [{}]
        else:
            case_list = [dict(case) for case in cases]
        rng = random.Random(payload.random_seed)
        if payload.randomize_case_order:
            rng.shuffle(case_list)
        samples: list[BenchmarkSample] = []
        failed = False
        started = utc_now()
        for case_index, case in enumerate(case_list):
            case_key = ",".join(f"{key}={case[key]}" for key in sorted(case)) or f"case-{case_index}"
            total_iterations = payload.warmup_iterations + payload.measured_iterations
            for iteration in range(total_iterations):
                warmup = iteration < payload.warmup_iterations
                sample_started = utc_now()
                wall_start = time.perf_counter()
                try:
                    result = executor(case, iteration, warmup)
                    elapsed_ms = (time.perf_counter() - wall_start) * 1000
                    measurement = result if isinstance(result, BenchmarkMeasurement) else BenchmarkMeasurement(metrics=result)
                    metrics = {key: float(value) for key, value in measurement.metrics.items()}
                    metrics.setdefault("wall_time_ms", elapsed_ms)
                    sample = BenchmarkSample(
                        case_key=case_key,
                        iteration=iteration,
                        warmup=warmup,
                        dimensions=case,
                        metrics=metrics,
                        scenario_run_ref=measurement.scenario_run_ref,
                        analysis_run_ref=measurement.analysis_run_ref,
                        valid=measurement.valid,
                        excluded_reason=measurement.excluded_reason,
                        started_at=sample_started,
                        completed_at=utc_now(),
                    )
                except Exception as exc:  # benchmark corpus must retain failed samples
                    failed = True
                    sample = BenchmarkSample(
                        case_key=case_key,
                        iteration=iteration,
                        warmup=warmup,
                        dimensions=case,
                        metrics={"wall_time_ms": (time.perf_counter() - wall_start) * 1000},
                        valid=False,
                        excluded_reason=f"{type(exc).__name__}: {exc}",
                        started_at=sample_started,
                        completed_at=utc_now(),
                    )
                samples.append(sample)
        measured = [sample for sample in samples if not sample.warmup and sample.valid]
        distributions: list[MetricDistribution] = []
        metric_keys = sorted({key for sample in measured for key in sample.metrics})
        for metric_key in metric_keys:
            distributions.append(
                summarize_metric(
                    metric_key,
                    [sample.metrics[metric_key] for sample in measured if metric_key in sample.metrics],
                    outlier_policy=str(payload.outlier_policy),
                    confidence_level=payload.confidence_level,
                )
            )
        assessments: list[ScalingAssessment] = []
        dimension = independent_dimension or (payload.dimensions[0].dimension_key if len(payload.dimensions) == 1 else None)
        if dimension:
            grouped: dict[tuple[str, float], list[float]] = {}
            for sample in measured:
                raw_x = sample.dimensions.get(dimension)
                if not isinstance(raw_x, (int, float)):
                    continue
                for metric_key, value in sample.metrics.items():
                    grouped.setdefault((metric_key, float(raw_x)), []).append(float(value))
            for metric_key in metric_keys:
                points = [(x, statistics.median(values)) for (key, x), values in grouped.items() if key == metric_key]
                if points:
                    assessments.append(analyze_scaling(metric_key=metric_key, independent_dimension=dimension, points=points))
        status = BenchmarkStatus.FAILED if failed and not measured else (BenchmarkStatus.DEGRADED if failed else BenchmarkStatus.COMPLETED)
        artifact = ExperimentSeriesArtifact(
            artifact_id=new_artifact_id("expser"),
            producer=self.producer,
            provenance=Provenance(
                input_refs=(protocol.reference(),),
                derivation_key="benchmark-series.v1",
                notes=(f"Started at {started.isoformat()}",),
            ),
            payload=ExperimentSeriesPayload(
                protocol_ref=protocol.reference(),
                status=status,
                independent_dimension=dimension,
                samples=tuple(samples),
                distributions=tuple(distributions),
                scaling_assessments=tuple(assessments),
                environment_refs=environment_refs,
                comparability_notes=comparability_notes,
                limitations=(
                    "Timing intervals are descriptive and do not prove causal improvement without controlled comparability.",
                ),
            ),
        )
        return artifact.seal()
