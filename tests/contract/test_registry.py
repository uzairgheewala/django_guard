from __future__ import annotations

import pytest
from pydantic import BaseModel

from planguard.artifacts.registry import ExtensionRegistry
from planguard.errors import ArtifactValidationError, RegistryConflictError


class DemoExtension(BaseModel):
    enabled: bool
    threshold: int


def test_registered_extension_is_validated() -> None:
    registry = ExtensionRegistry()
    registry.register("dev.example.demo", DemoExtension)
    value = registry.validate(
        {"dev.example.demo": {"enabled": True, "threshold": 4}}
    )
    assert value == {"dev.example.demo": {"enabled": True, "threshold": 4}}


def test_unknown_extension_round_trips() -> None:
    registry = ExtensionRegistry()
    payload = {"future.vendor.feature": {"opaque": [1, 2, 3]}}
    assert registry.validate(payload) == payload


def test_invalid_registered_extension_is_rejected() -> None:
    registry = ExtensionRegistry()
    registry.register("dev.example.demo", DemoExtension)
    with pytest.raises(ArtifactValidationError):
        registry.validate({"dev.example.demo": {"enabled": True}})


def test_registry_rejects_accidental_overwrite() -> None:
    registry = ExtensionRegistry()
    registry.register("dev.example.demo", DemoExtension)
    with pytest.raises(RegistryConflictError):
        registry.register("dev.example.demo", DemoExtension)
