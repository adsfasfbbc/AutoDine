from __future__ import annotations

from pathlib import Path
import sys

from fastapi.testclient import TestClient
from sqlalchemy import select


ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autodine_core.main import create_app
from autodine_core.modules.alarm.models import Alarm, AlarmStatus
from autodine_core.modules.device.models import DeviceCommand, DeviceCommandStatus
from autodine_core.modules.event.models import EventOutbox
from autodine_core.modules.queue.models import QueueSnapshot


def _build_client() -> TestClient:
    app = create_app(database_url="sqlite+pysqlite:///:memory:")
    app.state.metadata.create_all(app.state.engine)
    return TestClient(app)


def _event(*, event_type: str, event_id: str, payload: dict, severity: str = "info") -> dict:
    return {
        "protocol": "ADP",
        "version": "1.0",
        "event_id": event_id,
        "trace_id": "trace-" + event_id,
        "event_type": event_type,
        "severity": severity,
        "timestamp": "2026-08-21T10:30:00Z",
        "store_id": "store-1",
        "source": {"module": "operator", "device_id": "machine-1"},
        "payload": payload,
    }


def test_queue_updated_event_upserts_latest_store_zone_snapshot_and_outbox() -> None:
    client = _build_client()

    response = client.post(
        "/api/v1/events",
        json=_event(
            event_type="queue.updated",
            event_id="queue-1",
            payload={"zone_id": "pickup", "waiting_count": 3, "estimated_wait_seconds": 120},
        ),
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "processed"
    assert client.get("/api/v1/queues/store-1").json()["data"]["items"] == [
        {"zone_id": "pickup", "waiting_count": 3, "estimated_wait_seconds": 120}
    ]
    session = client.app.state.session_factory()
    snapshot = session.get(QueueSnapshot, ("store-1", "pickup"))
    assert snapshot.waiting_count == 3
    assert session.scalar(select(EventOutbox.event_type).where(EventOutbox.event_type == "queue.updated")) == "queue.updated"
    session.close()


def test_device_command_stays_pending_until_result_event_then_is_recorded() -> None:
    client = _build_client()

    command = client.post(
        "/api/v1/devices/machine-1/commands",
        json={"store_id": "store-1", "command_type": "clean", "parameters": {"mode": "quick"}},
    )

    assert command.status_code == 200
    command_id = command.json()["data"]["command_id"]
    assert command.json()["data"]["status"] == "PENDING"
    result = client.post(
        "/api/v1/events",
        json=_event(
            event_type="device.command_result",
            event_id="device-result-1",
            payload={"command_id": command_id, "status": "SUCCEEDED", "result": {"cycles": 1}},
        ),
    )

    assert result.status_code == 200
    listed = client.get("/api/v1/devices/machine-1/commands?store_id=store-1")
    assert listed.json()["data"]["items"][0]["command_id"] == command_id
    session = client.app.state.session_factory()
    saved = session.get(DeviceCommand, command_id)
    assert saved.status is DeviceCommandStatus.SUCCEEDED
    assert saved.result == {"cycles": 1}
    assert session.scalar(select(EventOutbox.event_type).where(EventOutbox.event_type == "device.command_result")) == "device.command_result"
    session.close()


def test_alarm_open_acknowledge_resolve_is_idempotent_by_source_key() -> None:
    client = _build_client()
    payload = {"store_id": "store-1", "source_key": "machine-1:overheat", "severity": "critical", "message": "overheat"}

    opened = client.post("/api/v1/alarms", json=payload)
    duplicate = client.post("/api/v1/alarms", json=payload)
    alarm_id = opened.json()["data"]["alarm_id"]
    acknowledged = client.post("/api/v1/alarms/" + alarm_id + "/acknowledge")
    resolved = client.post("/api/v1/alarms/" + alarm_id + "/resolve")

    assert duplicate.json()["data"]["alarm_id"] == alarm_id
    assert acknowledged.json()["data"]["status"] == "ACKNOWLEDGED"
    assert resolved.json()["data"]["status"] == "RESOLVED"
    assert client.get("/api/v1/alarms?store_id=store-1").json()["data"]["items"][0]["alarm_id"] == alarm_id
    session = client.app.state.session_factory()
    alarm = session.get(Alarm, alarm_id)
    assert alarm.status is AlarmStatus.RESOLVED
    assert len(session.scalars(select(Alarm)).all()) == 1
    assert [item[0] for item in session.execute(select(EventOutbox.event_type).where(EventOutbox.event_type.like("alarm.%")).order_by(EventOutbox.created_at)).all()] == [
        "alarm.opened", "alarm.acknowledged", "alarm.resolved"
    ]
    session.close()


def test_analytics_summary_reads_core_truth_with_window_and_definitions() -> None:
    client = _build_client()
    client.post(
        "/api/v1/alarms",
        json={"store_id": "store-1", "source_key": "machine-1:door", "severity": "warning", "message": "door open"},
    )

    response = client.get("/api/v1/analytics/summary?store_id=store-1&start=2026-08-01T00:00:00Z&end=2026-08-31T00:00:00Z")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["window"] == {"start": "2026-08-01T00:00:00+00:00", "end": "2026-08-31T00:00:00+00:00"}
    assert data["metrics"]["open_alarm_count"] == 1
    assert data["definitions"]["open_alarm_count"] == "Alarms still open or acknowledged at query time."


def test_websocket_manager_fans_out_adp_envelope_only_to_same_store() -> None:
    client = _build_client()

    with client.websocket_connect("/ws/stores/store-1") as subscribed:
        client.app.state.event_publisher.publish(
            _event(event_type="queue.updated", event_id="ws-queue-1", payload={"zone_id": "pickup", "waiting_count": 1})
        )
        message = subscribed.receive_json()

    assert message["event_id"] == "ws-queue-1"
    assert message["event_type"] == "queue.updated"
    assert message["store_id"] == "store-1"
