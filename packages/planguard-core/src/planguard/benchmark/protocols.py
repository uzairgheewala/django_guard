"""Built-in benchmark protocols expressed as immutable semantic artifacts."""

from __future__ import annotations

from planguard.artifacts.models import (
    BenchmarkDimension,
    BenchmarkProtocolArtifact,
    BenchmarkProtocolPayload,
    CacheProtocol,
    OutlierPolicy,
    ProducerIdentity,
    Provenance,
)
from planguard.canonical import canonical_json_bytes
from planguard.ids import content_derived_id
from planguard.time import semantic_epoch


def _artifact(payload: BenchmarkProtocolPayload, producer: ProducerIdentity) -> BenchmarkProtocolArtifact:
    identity = content_derived_id(
        "bproto",
        canonical_json_bytes({"payload": payload, "producer": producer.model_dump(mode="python")}),
        length=32,
    )
    return BenchmarkProtocolArtifact(
        artifact_id=identity,
        created_at=semantic_epoch(),
        producer=producer,
        provenance=Provenance(derivation_key="builtin-benchmark-protocol.v1"),
        payload=payload,
    ).seal()


def builtin_benchmark_protocols(producer: ProducerIdentity) -> tuple[BenchmarkProtocolArtifact, ...]:
    interactive = BenchmarkProtocolPayload(
        protocol_key="interactive-read-series.v1",
        title="Interactive read scaling series",
        warmup_iterations=2,
        measured_iterations=7,
        cache_protocol=CacheProtocol.COLD_THEN_WARM,
        outlier_policy=OutlierPolicy.MAD,
        timeout_seconds=30,
        dimensions=(
            BenchmarkDimension(
                dimension_key="parent_count",
                values=(1, 10, 100, 1000),
                unit="rows",
            ),
        ),
        required_environment_fields=(
            "python_version",
            "database.vendor",
            "machine_profile",
        ),
        notes=(
            "Structural query metrics remain authoritative when timing comparability is degraded.",
        ),
    )
    concurrent = BenchmarkProtocolPayload(
        protocol_key="concurrent-write-pressure.v1",
        title="Concurrent write pressure",
        warmup_iterations=1,
        measured_iterations=5,
        cache_protocol=CacheProtocol.WARM,
        outlier_policy=OutlierPolicy.IQR,
        timeout_seconds=60,
        concurrency_levels=(1, 2, 4, 8),
        dimensions=(
            BenchmarkDimension(
                dimension_key="concurrency",
                values=(1, 2, 4, 8),
                unit="workers",
            ),
        ),
        metrics=(
            "wall_time_ms",
            "throughput_ops_s",
            "error_count",
            "lock_wait_ms",
        ),
        notes=(
            "A concurrency series must report failed and timed-out workers rather than omitting them.",
        ),
    )
    plan_transition = BenchmarkProtocolPayload(
        protocol_key="plan-transition-series.v1",
        title="Data-scale and selectivity plan transition",
        warmup_iterations=1,
        measured_iterations=5,
        cache_protocol=CacheProtocol.MIXED,
        randomize_case_order=True,
        random_seed=31,
        outlier_policy=OutlierPolicy.MAD,
        dimensions=(
            BenchmarkDimension(
                dimension_key="logical_rows",
                values=(100, 1000, 10000, 100000),
                unit="rows",
            ),
            BenchmarkDimension(
                dimension_key="selectivity",
                values=("unique", "high", "medium", "low"),
                ordered=False,
            ),
        ),
        metrics=(
            "wall_time_ms",
            "database_time_ms",
            "shared_blocks_read",
            "query_count",
        ),
    )
    return tuple(_artifact(payload, producer) for payload in (interactive, concurrent, plan_transition))
