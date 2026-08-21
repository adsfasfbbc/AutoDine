from datetime import datetime, timezone
from pathlib import Path
import sys

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autodine_core.main import create_app


def test_health_endpoint_returns_core_status_payload() -> None:
    client = TestClient(create_app(database_url="sqlite+pysqlite:///:memory:"))

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "autodine_core"

    timestamp = datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))
    assert timestamp.tzinfo == timezone.utc
