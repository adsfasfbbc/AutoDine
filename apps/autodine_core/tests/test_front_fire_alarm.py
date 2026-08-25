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
from autodine_core.modules.device.models import DeviceCommand
from autodine_core.modules.event.models import EventInbox, EventInboxStatus, EventOutbox


def _build_client() -> TestClient:
    app = create_app(database_url="sqlite+pysqlite:///:memory:")
    app.state.metadata.create_all(app.state.engine)
    return TestClient(app)


def _register_device(client: TestClient, *, device_id: str, device_type: str, store_id: str = "store-1") -> None:
    response = client.post(
        "/api/v1/devices",
        json={"store_id": store_id, "device_id": device_id, "device_type": device_type},
    )
    assert response.status_code == 200


def _front_fire_event(*, event_id: str, severity: str = "critical", payload: dict | None = None) -> dict:
    return {
        "protocol": "ADP",
        "version": "1.0",
        "event_id": event_id,
        "trace_id": "trace-" + event_id,
        "event_type": "vision.front.fire",
        "severity": severity,
        "timestamp": "2026-08-21T10:30:00Z",
        "store_id": "store-1",
        "source": {"module": "front_vision", "device_id": "cam-front-01"},
        "payload": payload
        or {
            "event_subtype": "flame_dual_confirm",
            "confidence": 0.91,
            "vision_conf": 0.91,
            "sensor_state": 1,
            "duration_ms": 2500,
            "zone_id": "hall",
            "vote_count": 3,
            "abnormal_channels": ["vision", "flame", "temperature"],
            "triggered_rule": "vote3",
            "readings": {
                "temperature": 62,
                "humidity": 35,
                "tvoc": 210,
                "co2": 900,
                "pm25": 80,
                "light": 400,
                "flame": 1,
                "vision_conf": 0.91,
            },
        },
    }


def _count_rows(session: Session, model: object) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_vision_front_fire_opens_alarm_broadcasts_alarm_updated_and_fans_out_websocket() -> None:
    client = _build_client()

    with client.websocket_connect("/ws/stores/store-1") as subscribed:
        response = client.post(
            "/api/v1/events",
            json=_front_fire_event(event_id="evt-front-fire-1"),
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
    assert updated["payload"]["source_key"] == "front_fire:evt-front-fire-1"

    alarms = client.get("/api/v1/alarms?store_id=store-1").json()["data"]["items"]
    assert len(alarms) == 1
    alarm = alarms[0]
    assert alarm["severity"] == "critical"
    assert alarm["source_key"] == "front_fire:evt-front-fire-1"
    assert alarm["status"] == "OPEN"
    assert "flame_dual_confirm" in alarm["message"]
    assert "rule=vote3" in alarm["message"]
    assert "votes=3" in alarm["message"]
    assert "confidence=0.91" in alarm["message"]
    assert "sensor_state=1" in alarm["message"]
    assert "duration_ms=2500" in alarm["message"]

    session = client.app.state.session_factory()
    inbox = session.get(EventInbox, "evt-front-fire-1")
    assert inbox.status is EventInboxStatus.PROCESSED
    outbox = session.scalar(select(EventOutbox).where(EventOutbox.event_type == "alarm.updated"))
    assert outbox is not None
    assert outbox.severity == "critical"
    assert outbox.publish_status == "PUBLISHED"
    session.close()


def test_vision_front_fire_rejects_out_of_range_payload_without_inbox_or_outbox_residue() -> None:
    client = _build_client()

    response = client.post(
        "/api/v1/events",
        json=_front_fire_event(
            event_id="evt-front-fire-bad",
            payload={
                "event_subtype": "flame_dual_confirm",
                "confidence": 1.5,
                "vision_conf": 0.91,
                "sensor_state": 1,
                "duration_ms": 2500,
                "zone_id": "hall",
                "vote_count": 2,
                "abnormal_channels": ["vision", "flame"],
                "triggered_rule": "vision_flame",
                "readings": {"flame": 1, "vision_conf": 0.91},
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


def test_vision_front_fire_powers_off_shutdown_listed_devices() -> None:
    client = _build_client()
    _register_device(client, device_id="fan-01", device_type="fan")
    _register_device(client, device_id="ac-01", device_type="air_conditioner")
    _register_device(client, device_id="lamp-01", device_type="light")  # not on the shutdown list

    with client.websocket_connect("/ws/stores/store-1") as subscribed:
        response = client.post(
            "/api/v1/events",
            json=_front_fire_event(event_id="evt-front-fire-shutdown"),
        )
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "processed"
        messages = [subscribed.receive_json() for _ in range(4)]

    by_type = {}
    for message in messages:
        by_type.setdefault(message["event_type"], []).append(message)
    assert set(by_type) == {"alarm.opened", "alarm.updated", "device.command"}
    commands = by_type["device.command"]
    assert len(commands) == 2
    commanded = {c["payload"]["device_id"] for c in commands}
    assert commanded == {"fan-01", "ac-01"}
    for command in commands:
        assert command["payload"]["command_type"] == "power_off"
        assert command["payload"]["parameters"]["source_event_id"] == "evt-front-fire-shutdown"

    session = client.app.state.session_factory()
    rows = session.scalars(select(DeviceCommand)).all()
    assert len(rows) == 2
    assert {row.device_id for row in rows} == {"fan-01", "ac-01"}
    assert all(row.command_type == "power_off" for row in rows)
    session.close()


def test_vision_front_fire_without_matching_devices_only_opens_alarm() -> None:
    client = _build_client()
    _register_device(client, device_id="lamp-01", device_type="light")  # no fan/AC registered

    with client.websocket_connect("/ws/stores/store-1") as subscribed:
        response = client.post(
            "/api/v1/events",
            json=_front_fire_event(event_id="evt-front-fire-no-device"),
        )
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "processed"
        messages = [subscribed.receive_json(), subscribed.receive_json()]

    assert {m["event_type"] for m in messages} == {"alarm.opened", "alarm.updated"}

    session = client.app.state.session_factory()
    assert _count_rows(session, DeviceCommand) == 0
    assert _count_rows(session, Alarm) == 1
    session.close()
