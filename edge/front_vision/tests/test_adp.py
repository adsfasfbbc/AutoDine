"""Unit tests for ADP envelope construction, schema validation and publishing."""
from __future__ import annotations

import httpx
import pytest

from front_vision.adp import AdpPublisher, build_envelope, validate_envelope
from front_vision.config import ENVELOPE_SCHEMA_PATH

BASE_KWARGS = dict(store_id="store-main", device_id="front-cam-01")


def test_queue_updated_envelope_validates() -> None:
    envelope = build_envelope(
        event_type="queue.updated",
        payload={"zone_id": "front-queue", "waiting_count": 3},
        **BASE_KWARGS,
    )
    validate_envelope(envelope, ENVELOPE_SCHEMA_PATH)


def test_experience_summary_envelope_validates() -> None:
    envelope = build_envelope(
        event_type="customer.experience_summary",
        payload={
            "sample_count": 12,
            "positive_ratio": 0.5,
            "neutral_ratio": 0.25,
            "negative_ratio": 0.25,
        },
        **BASE_KWARGS,
    )
    validate_envelope(envelope, ENVELOPE_SCHEMA_PATH)


def test_envelope_rejects_bad_event_type() -> None:
    from jsonschema import ValidationError

    envelope = build_envelope(
        event_type="not_a_namespace", payload={}, **BASE_KWARGS
    )
    with pytest.raises(ValidationError):
        validate_envelope(envelope, ENVELOPE_SCHEMA_PATH)


def test_envelope_fields() -> None:
    envelope = build_envelope(event_type="queue.updated", payload={"zone_id": "z", "waiting_count": 0}, **BASE_KWARGS)
    assert envelope["protocol"] == "ADP"
    assert envelope["version"] == "1.0"
    assert envelope["source"] == {"module": "front_vision", "device_id": "front-cam-01"}
    assert envelope["severity"] == "info"
    assert envelope["trace_id"]


def _publisher(handler, **kwargs) -> AdpPublisher:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return AdpPublisher(
        core_url="http://core.test",
        schema_path=ENVELOPE_SCHEMA_PATH,
        retries=kwargs.pop("retries", 3),
        backoff_seconds=0.0,
        client=client,
        **kwargs,
    )


def test_publish_success() -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"status": "processed"})

    pub = _publisher(handler)
    envelope = pub.publish(event_type="queue.updated", payload={"zone_id": "front-queue", "waiting_count": 2}, **BASE_KWARGS)
    assert envelope is not None
    assert len(seen) == 1
    assert str(seen[0].url) == "http://core.test/api/v1/events"


def test_publish_retries_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(500, json={"detail": "boom"})
        return httpx.Response(200, json={"status": "processed"})

    pub = _publisher(handler, retries=3)
    envelope = pub.publish(event_type="queue.updated", payload={"zone_id": "front-queue", "waiting_count": 1}, **BASE_KWARGS)
    assert envelope is not None
    assert calls["n"] == 3


def test_publish_gives_up_after_retries() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={"detail": "boom"})

    pub = _publisher(handler, retries=3)
    envelope = pub.publish(event_type="queue.updated", payload={"zone_id": "front-queue", "waiting_count": 1}, **BASE_KWARGS)
    assert envelope is None
    assert calls["n"] == 3
