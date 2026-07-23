from __future__ import annotations

from planguard.artifacts.models import ProducerIdentity
from planguard.benchmark import BenchmarkMeasurement, BenchmarkRunner, analyze_scaling, builtin_benchmark_protocols, summarize_metric


def test_robust_distribution_excludes_extreme_outlier() -> None:
    distribution = summarize_metric("latency_ms", [10, 11, 9, 10, 1000], outlier_policy="mad")
    assert distribution.sample_count == 4
    assert distribution.excluded_count == 1
    assert distribution.median == 10
    assert distribution.p95 is not None


def test_scaling_classification_is_descriptive() -> None:
    linear = analyze_scaling(metric_key="queries", independent_dimension="rows", points=[(1, 2), (10, 20), (100, 200), (1000, 2000)])
    assert str(linear.classification) == "approximately_linear"
    assert linear.confidence > 0.99
    threshold = analyze_scaling(metric_key="latency", independent_dimension="rows", points=[(1, 5), (10, 6), (100, 7), (1000, 500)])
    assert str(threshold.classification) == "threshold_transition"


def test_runner_retains_failed_samples_and_reports_degraded() -> None:
    producer = ProducerIdentity(name="test", version="1")
    protocol = builtin_benchmark_protocols(producer)[0]
    calls = 0
    def executor(case, iteration, warmup):
        nonlocal calls
        calls += 1
        if not warmup and case["parent_count"] == 100 and iteration == protocol.payload.warmup_iterations:
            raise RuntimeError("injected")
        scale = float(case["parent_count"])
        return BenchmarkMeasurement(metrics={"wall_time_ms": scale, "query_count": scale})
    series = BenchmarkRunner(producer=producer).run(protocol, executor)
    assert calls == 4 * (protocol.payload.warmup_iterations + protocol.payload.measured_iterations)
    assert str(series.payload.status) == "degraded"
    assert any(not sample.valid for sample in series.payload.samples)
    assert series.verify_integrity()


def test_concurrent_operation_retains_worker_metrics() -> None:
    from planguard.benchmark import run_concurrent_operation
    measurement = run_concurrent_operation(4, lambda index: {"lock_wait_ms": float(index), "ops": 1.0})
    assert measurement.valid
    assert measurement.metrics["ops"] == 4
    assert measurement.metrics["lock_wait_ms"] == 6
    assert measurement.metrics["error_count"] == 0
