from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, strategies as st  # noqa: E402

from planguard.artifacts.codec import build_default_codec  # noqa: E402
from planguard.artifacts.models import (  # noqa: E402
    CapturePolicyArtifact,
    CapturePolicyPayload,
    ProducerIdentity,
)
from planguard.canonical import canonical_json_bytes  # noqa: E402

json_scalars = st.none() | st.booleans() | st.integers() | st.text()
json_values = st.recursive(
    json_scalars,
    lambda children: st.lists(children, max_size=5)
    | st.dictionaries(st.text(min_size=1, max_size=12), children, max_size=5),
    max_leaves=20,
)


@given(json_values)
def test_canonicalization_is_idempotent(value) -> None:
    first = canonical_json_bytes(value)
    second = canonical_json_bytes(json.loads(first))
    assert first == second


@given(st.text(min_size=1, max_size=40))
def test_sealed_artifact_round_trips_for_policy_keys(policy_key: str) -> None:
    codec = build_default_codec()
    artifact = CapturePolicyArtifact(
        artifact_id="cap_property_test",
        created_at=datetime(2026, 7, 23, tzinfo=UTC),
        producer=ProducerIdentity(name="property-test", version="0.1"),
        payload=CapturePolicyPayload(policy_key=policy_key),
    )
    assert codec.decode(codec.encode(artifact)).payload.policy_key == policy_key
