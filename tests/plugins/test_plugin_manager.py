from __future__ import annotations

import pytest

from planguard.artifacts.models import ProducerIdentity
from planguard.errors import RegistryConflictError
from planguard.plugins import PluginManager, builtin_plugin_manifests


def test_builtin_plugin_manifests_are_stable_and_registerable() -> None:
    producer = ProducerIdentity(name="test", version="1")
    first = builtin_plugin_manifests(producer)
    second = builtin_plugin_manifests(producer)
    assert [item.artifact_id for item in first] == [item.artifact_id for item in second]
    manager = PluginManager(producer=producer, capabilities={"query.family", "workload.graph", "postgresql.plan_json", "scenario.execution", "query.capture.manual"})
    for manifest in first:
        manager.register(manifest)
    assert len(manager.manifests()) == 6
    with pytest.raises(RegistryConflictError):
        manager.register(first[0])


def test_enabled_plugin_rejects_missing_capability() -> None:
    producer = ProducerIdentity(name="test", version="1")
    manifest = next(item for item in builtin_plugin_manifests(producer) if item.payload.required_capabilities)
    with pytest.raises(ValueError):
        PluginManager(producer=producer, capabilities=set()).register(manifest)


def test_plugin_execution_isolated_by_timeout_contract() -> None:
    producer = ProducerIdentity(name="test", version="1")
    manifest = builtin_plugin_manifests(producer)[-1]
    manager = PluginManager(producer=producer)
    manager.register(manifest, lambda value: value + 1)
    result = manager.execute(manifest.payload.plugin_key, 4, timeout_seconds=1)
    assert result.status == "completed"
    assert result.result == 5
