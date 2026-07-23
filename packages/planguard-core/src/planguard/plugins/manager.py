"""Versioned plugin contracts and conservative entry-point discovery."""

from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from importlib import metadata
from typing import Any

from planguard.artifacts.models import (
    PluginComponentType,
    PluginDeterminism,
    PluginManifestArtifact,
    PluginManifestPayload,
    ProducerIdentity,
    Provenance,
)
from planguard.canonical import canonical_json_bytes
from planguard.errors import RegistryConflictError
from planguard.ids import content_derived_id
from planguard.time import semantic_epoch


@dataclass(frozen=True, slots=True)
class PluginExecutionResult:
    plugin_key: str
    status: str
    result: Any | None = None
    error: str | None = None
    timed_out: bool = False


@dataclass(frozen=True, slots=True)
class PluginLoadResult:
    manifest: PluginManifestArtifact
    loaded: bool
    component: Any | None = None
    error: str | None = None


def _manifest(payload: PluginManifestPayload, producer: ProducerIdentity) -> PluginManifestArtifact:
    artifact_id = content_derived_id(
        "plug",
        canonical_json_bytes({"payload": payload, "producer": producer.model_dump(mode="python")}),
        length=32,
    )
    return PluginManifestArtifact(
        artifact_id=artifact_id,
        created_at=semantic_epoch(),
        producer=producer,
        provenance=Provenance(derivation_key="builtin-plugin-manifest.v1"),
        payload=payload,
    ).seal()


def builtin_plugin_manifests(producer: ProducerIdentity) -> tuple[PluginManifestArtifact, ...]:
    specs = (
        PluginManifestPayload(
            plugin_key="core.detectors.v1",
            plugin_version="1.0.0",
            package_name="planguard",
            entry_point_name="core-detectors",
            component_type=PluginComponentType.DETECTOR,
            required_capabilities=("query.family", "workload.graph"),
            accepted_schema_versions=("planguard.analysis-summary.v1", "planguard.workload-graph.v1"),
            emitted_schema_versions=("planguard.finding.v1", "planguard.detector-receipt.v1"),
            determinism=PluginDeterminism.DETERMINISTIC,
            enabled_by_default=True,
            description="Built-in query and workload pathology detectors.",
        ),
        PluginManifestPayload(
            plugin_key="core.postgres-plans.v1",
            plugin_version="1.0.0",
            package_name="planguard",
            entry_point_name="postgres-plan-extractors",
            component_type=PluginComponentType.PLAN_EXTRACTOR,
            required_capabilities=("postgresql.plan_json",),
            accepted_schema_versions=("planguard.plan-observation.v1",),
            emitted_schema_versions=("planguard.finding.v1",),
            determinism=PluginDeterminism.DETERMINISTIC,
            enabled_by_default=True,
            description="Canonical PostgreSQL plan normalization and feature extraction.",
        ),
        PluginManifestPayload(
            plugin_key="core.academic-lab.v1",
            plugin_version="1.0.0",
            package_name="planguard",
            entry_point_name="academic-lab",
            component_type=PluginComponentType.SCENARIO_ADAPTER,
            required_capabilities=("scenario.execution", "query.capture.manual"),
            emitted_schema_versions=("planguard.scenario-run.v1", "planguard.dataset-manifest.v1"),
            determinism=PluginDeterminism.DETERMINISTIC,
            enabled_by_default=True,
            description="Deterministic multi-tenant academic workload laboratory.",
        ),
        PluginManifestPayload(
            plugin_key="core.coverage.v1",
            plugin_version="1.0.0",
            package_name="planguard",
            entry_point_name="coverage-strategies",
            component_type=PluginComponentType.COVERAGE_STRATEGY,
            accepted_schema_versions=("planguard.universe-profile.v1",),
            emitted_schema_versions=("planguard.representative-set.v1", "planguard.coverage-report.v1"),
            determinism=PluginDeterminism.DETERMINISTIC,
            enabled_by_default=True,
            description="Partition, pairwise, motif, mutation, and metamorphic coverage strategies.",
        ),
        PluginManifestPayload(
            plugin_key="core.filesystem-store.v1",
            plugin_version="1.0.0",
            package_name="planguard",
            entry_point_name="filesystem-store",
            component_type=PluginComponentType.ARTIFACT_STORE,
            accepted_schema_versions=("planguard.any-artifact.v1",),
            emitted_schema_versions=("planguard.any-artifact.v1",),
            determinism=PluginDeterminism.ENVIRONMENT_DEPENDENT,
            safety_profile={"atomic_writes": True, "content_addressed": True, "network_access": False},
            enabled_by_default=True,
            description="Immutable content-addressed local artifact store.",
        ),
        PluginManifestPayload(
            plugin_key="core.reporters.v1",
            plugin_version="1.0.0",
            package_name="planguard",
            entry_point_name="reporters",
            component_type=PluginComponentType.REPORTER,
            accepted_schema_versions=("planguard.analysis-summary.v1", "planguard.comparison-report.v1"),
            determinism=PluginDeterminism.DETERMINISTIC,
            enabled_by_default=True,
            description="Terminal, JSON, and standalone HTML reporters.",
        ),
    )
    return tuple(_manifest(payload, producer) for payload in specs)


class PluginManager:
    def __init__(self, *, producer: ProducerIdentity, capabilities: set[str] | None = None) -> None:
        self.producer = producer
        self.capabilities = set(capabilities or ())
        self._manifests: dict[str, PluginManifestArtifact] = {}
        self._components: dict[str, Any] = {}

    def register(self, manifest: PluginManifestArtifact, component: Any | None = None, *, overwrite: bool = False) -> None:
        key = manifest.payload.plugin_key
        if key in self._manifests and not overwrite:
            raise RegistryConflictError(key)
        missing = set(manifest.payload.required_capabilities) - self.capabilities
        if missing and manifest.payload.enabled_by_default:
            raise ValueError(f"Plugin {key} requires unavailable capabilities: {sorted(missing)}")
        self._manifests[key] = manifest
        if component is not None:
            self._components[key] = component

    def manifests(self) -> tuple[PluginManifestArtifact, ...]:
        return tuple(self._manifests[key] for key in sorted(self._manifests))

    def get(self, plugin_key: str) -> Any | None:
        return self._components.get(plugin_key)


    def execute(self, plugin_key: str, *args: Any, timeout_seconds: float = 30.0, **kwargs: Any) -> PluginExecutionResult:
        component = self._components.get(plugin_key)
        if component is None:
            return PluginExecutionResult(plugin_key=plugin_key, status="not_loaded", error="Plugin component is not loaded")
        target = component.run if hasattr(component, "run") else component
        if not callable(target):
            return PluginExecutionResult(plugin_key=plugin_key, status="invalid", error="Plugin component is not callable")
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="planguard-plugin")
        future = executor.submit(target, *args, **kwargs)
        try:
            result = future.result(timeout=timeout_seconds)
            return PluginExecutionResult(plugin_key=plugin_key, status="completed", result=result)
        except FutureTimeoutError:
            future.cancel()
            return PluginExecutionResult(plugin_key=plugin_key, status="timed_out", error=f"Execution exceeded {timeout_seconds} seconds", timed_out=True)
        except Exception as exc:
            return PluginExecutionResult(plugin_key=plugin_key, status="failed", error=f"{type(exc).__name__}: {exc}")
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def discover(self, group: str = "planguard.plugins") -> tuple[PluginLoadResult, ...]:
        results: list[PluginLoadResult] = []
        entry_points = metadata.entry_points()
        selected = entry_points.select(group=group) if hasattr(entry_points, "select") else entry_points.get(group, ())
        for entry_point in selected:
            try:
                loaded = entry_point.load()
                declared = loaded() if callable(loaded) and not isinstance(loaded, PluginManifestArtifact) else loaded
                if isinstance(declared, tuple) and len(declared) == 2:
                    manifest, component = declared
                else:
                    manifest, component = declared, loaded
                if not isinstance(manifest, PluginManifestArtifact):
                    raise TypeError("Plugin entry point must expose PluginManifestArtifact or (manifest, component)")
                self.register(manifest, component)
                results.append(PluginLoadResult(manifest=manifest, loaded=True, component=component))
            except Exception as exc:
                payload = PluginManifestPayload(
                    plugin_key=f"discovery-error.{entry_point.name}",
                    plugin_version="0",
                    package_name=getattr(entry_point, "module", "unknown"),
                    entry_point_group=group,
                    entry_point_name=entry_point.name,
                    component_type=PluginComponentType.REPORTER,
                    determinism=PluginDeterminism.NONDETERMINISTIC,
                    enabled_by_default=False,
                    description="Synthetic manifest for a failed plugin discovery attempt.",
                )
                manifest = _manifest(payload, self.producer)
                results.append(PluginLoadResult(manifest=manifest, loaded=False, error=f"{type(exc).__name__}: {exc}"))
        return tuple(results)
