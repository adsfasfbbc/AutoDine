from __future__ import annotations

from pathlib import Path
import sys

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session


ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autodine_core.main import create_app
from autodine_core.modules.alarm.models import Alarm
from autodine_core.modules.event.models import EventInbox, EventInboxStatus, EventOutbox


def _build_client() -> TestClient:
    app = create_app(database_url="sqlite+pysqlite:///:memory:")
    app.state.metadata.create_all(app.state.engine)
    return TestClient(app)


def _front_safety_event(*, event_id: str, severity: str = "critical", payload: dict | None = None) -> dict:
    return {
        "protocol": "ADP",
        "version": "1.0",
        "event_id": event_id,
        "trace_id": "trace-" + event_id,
        "event_type": "vision.front.safety",
        "severity": severity,
        "timestamp": "2026-08-21T10:30:00Z",
        "store_id": "store-1",
        "source": {"module": "front_vision", "device_id": "cam-front-01"},
        "payload": payload
        or {
            "event_subtype": "violent_interaction",
            "confidence": 0.92,
            "vision_score": 0.95,
            "audio_score": 0.88,
            "duration_ms": 3200,
            "zone_id": "hall",
        },
    }


def _count_rows(session: Session, model: object) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_vision_front_safety_opens_alarm_broadcasts_alarm_updated_and_fans_out_websocket() -> None:
    client = _build_client()

    with client.websocket_connect("/ws/stores/store-1") as subscribed:
        response = client.post(
            "/api/v1/events",
            json=_front_safety_event(event_id="evt-front-safety-1"),
        )
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "processed"
        messages = [subscribed.receive_json(), subscribed.receive_json()]

    by_type = {message["event_type"]: message for message in messages}
    assert set(by_type) == {"alarm.opened", "alarm.updated"}
    updated = by_type["alarm.updated"]
    assert updated["event_id"].startswith("outbox-")
    assert updated["store_id"] == "store-1"
    assert updated["severity"] == "critical"
    assert updated["payload"]["source_key"] == "front_safety:evt-front-safety-1"

    alarms = client.get("/api/v1/alarms?store_id=store-1").json()["data"]["items"]
    assert len(alarms) == 1
    alarm = alarms[0]
    assert alarm["severity"] == "critical"
    assert alarm["source_key"] == "front_safety:evt-front-safety-1"
    assert alarm["status"] == "OPEN"
    assert "violent_interaction" in alarm["message"]
    assert "confidence=0.92" in alarm["message"]
    assert "duration_ms=3200" in alarm["message"]

    session = client.app.state.session_factory()
    inbox = session.get(EventInbox, "evt-front-safety-1")
    assert inbox.status is EventInboxStatus.PROCESSED
    outbox = session.scalar(select(EventOutbox).where(EventOutbox.event_type == "alarm.updated"))
    assert outbox is not None
    assert outbox.severity == "critical"
    assert outbox.publish_status == "PUBLISHED"
    session.close()


def test_vision_front_safety_rejects_out_of_range_payload_without_inbox_or_outbox_residue() -> None:
    client = _build_client()

    response = client.post(
        "/api/v1/events",
        json=_front_safety_event(
            event_id="evt-front-safety-bad",
            payload={
                "event_subtype": "violent_interaction",
                "confidence": 1.5,
                "vision_score": 0.95,
                "audio_score": 0.88,
                "duration_ms": 3200,
                "zone_id": "hall",
            },
        ),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_EVENT_ENVELOPE"

    session = client.app.state.session_factory()
    assert _count_rows(session, EventInbox) == 0
    assert _count_rows(session, EventOutbox) == 0
    assert _count_rows(session, Alarm) == 0
    session.close()
