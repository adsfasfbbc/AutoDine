from __future__ import annotations

import json
import sys
import subprocess
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from smart_storage_vision.backends import FRUIT_LABELS, MockBackend
from smart_storage_vision.models import IngredientCalibration
from smart_storage_vision.pipeline import SmartStoragePipeline


REPO_ROOT = Path(__file__).resolve().parents[3]
CORE_SOURCE = REPO_ROOT / "apps" / "autodine_core" / "src"
if str(CORE_SOURCE) not in sys.path:
    sys.path.insert(0, str(CORE_SOURCE))

from autodine_core.main import create_app


def test_yolo_fruit_ids_match_core_catalog() -> None:
    catalog = json.loads((REPO_ROOT / "data" / "seed" / "catalog.json").read_text(encoding="utf-8"))
    ingredients = {item["ingredient_id"]: item for item in catalog["ingredients"]}
    for ingredient_id in FRUIT_LABELS:
        assert ingredients[ingredient_id]["unit"] == "pcs"


def test_generated_business_events_are_accepted_by_core(tmp_path: Path) -> None:
    database_url = "sqlite+pysqlite:///" + str(tmp_path / "core.db")
    seed = subprocess.run(
        [sys.executable, "scripts/seed_data.py", "--database-url", database_url],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert seed.returncode == 0, seed.stderr
    app = create_app(database_url=database_url)
    client = TestClient(app)
    pipeline = SmartStoragePipeline(
        backend=MockBackend(),
        calibrations=[
            IngredientCalibration("lemon", "g", Decimal("120")),
            IngredientCalibration("tomato", "g", Decimal("100")),
        ],
        store_id="store-main",
        device_id="storage-cam-01",
    )
    _, events = pipeline.analyze(Path(__file__).resolve().parents[1] / "data" / "mock_scene.json")
    responses = [client.post("/api/v1/events", json=event) for event in events]
    assert all(response.status_code == 200 for response in responses)
    statuses = {response.json()["data"]["status"] for response in responses}
    assert statuses == {"processed"}
