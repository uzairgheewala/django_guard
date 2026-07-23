"""Entry-point factories for PlanGuard's built-in components."""

from __future__ import annotations

from planguard.artifacts.models import ProducerIdentity
from planguard.lab.academic import AcademicLabAdapter
from planguard.plugins.manager import builtin_plugin_manifests


def _by_key(key: str):
    producer = ProducerIdentity(name="planguard", version="0.7.0", build="entry-point")
    return next(item for item in builtin_plugin_manifests(producer) if item.payload.plugin_key == key)


def academic_lab_plugin():
    return _by_key("core.academic-lab.v1"), AcademicLabAdapter


def filesystem_store_plugin():
    from planguard.store.filesystem import FilesystemArtifactStore
    return _by_key("core.filesystem-store.v1"), FilesystemArtifactStore


def reporter_plugin():
    from planguard.reporting import render_html, render_json, render_terminal
    return _by_key("core.reporters.v1"), (render_terminal, render_json, render_html)
