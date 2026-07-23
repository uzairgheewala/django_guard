from __future__ import annotations

import json
import os

import pytest

pytest.importorskip("django")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "workbench_api.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.test import Client, override_settings  # noqa: E402

from planguard.artifacts.codec import default_codec  # noqa: E402
from planguard.artifacts.models import (  # noqa: E402
    CapturePolicyArtifact,
    CapturePolicyPayload,
    ProducerIdentity,
)
from planguard.store.filesystem import FilesystemArtifactStore  # noqa: E402

from api.views import artifact_index, artifact_store  # noqa: E402


@pytest.fixture
def api_client(tmp_path):
    store_path = tmp_path / "store"
    index_path = tmp_path / "registry.sqlite3"
    artifact_store.cache_clear()
    artifact_index.cache_clear()
    with override_settings(PLANGUARD_STORE=store_path, PLANGUARD_INDEX=index_path):
        yield Client(), FilesystemArtifactStore(store_path)
    artifact_index.cache_clear()
    artifact_store.cache_clear()


def test_health_and_capabilities(api_client) -> None:
    client, _ = api_client
    assert client.get("/api/v1/health").json()["milestone"] == "C"
    capabilities = client.get("/api/v1/capabilities").json()
    assert capabilities["capabilities"]["artifact.integrity"] == "supported"
    assert capabilities["capabilities"]["query.capture.django"] == "supported"


def test_list_detail_and_import(api_client) -> None:
    client, store = api_client
    artifact = CapturePolicyArtifact(
        artifact_id="cap_api_test",
        producer=ProducerIdentity(name="api-test", version="0.1"),
        payload=CapturePolicyPayload(policy_key="api.v1"),
    )
    encoded = default_codec.encode(artifact, pretty=True)
    response = client.post("/api/v1/import", data=encoded, content_type="application/json")
    assert response.status_code == 201
    assert store.verify("cap_api_test")

    listing = client.get("/api/v1/artifacts").json()
    assert listing["count"] == 1
    detail = client.get("/api/v1/artifacts/cap_api_test").json()
    assert detail["payload"]["policy_key"] == "api.v1"
