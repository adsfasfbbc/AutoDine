from __future__ import annotations

from pathlib import Path
import sys

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autodine_core.main import create_app


def _client() -> TestClient:
    app = create_app(database_url="sqlite+pysqlite:///:memory:")
    app.state.metadata.create_all(app.state.engine)
    return TestClient(app)


def test_unauthorized_storage_entry_opens_alarm() -> None:
    client = _client()
    event = {
        "protocol": "ADP",
        "version": "1.0",
        "event_id": "evt-storage-entry-1",
        "trace_id": "trace-storage-entry-1",
        "event_type": "vision.storage.security",
        "severity": "critical",
        "timestamp": "2026-08-23T12:00:00Z",
        "store_id": "store-1",
        "source": {"module": "smart_storage_vision", "device_id": "cam-storage-01"},
        "payload": {
            "event_subtype": "unauthorized_entry",
            "confidence": 0.91,
            "person_count": 1,
            "door_open": True,
            "authorization_present": False,
            "zone_id": "storage-door",
        },
    }
    response = client.post("/api/v1/events", json=event)
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "processed"
    alarm = client.get("/api/v1/alarms?store_id=store-1").json()["data"]["items"][0]
    assert alarm["severity"] == "critical"
    assert alarm["source_key"] == "storage_security:evt-storage-entry-1"
    assert "unauthorized_entry" in alarm["message"]

