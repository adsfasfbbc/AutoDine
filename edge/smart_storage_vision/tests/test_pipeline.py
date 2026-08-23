from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from jsonschema import Draft202012Validator

from smart_storage_vision.backends import MockBackend
from smart_storage_vision.models import IngredientCalibration
from smart_storage_vision.pipeline import SmartStoragePipeline
from smart_storage_vision.state import SnapshotStore


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_ROOT = Path(__file__).resolve().parents[1]


def build_pipeline(tmp_path: Path) -> SmartStoragePipeline:
    return SmartStoragePipeline(
        backend=MockBackend(),
        calibrations=[
            IngredientCalibration("lemon", "g", Decimal("120")),
            IngredientCalibration("tomato", "g", Decimal("100")),
        ],
        store_id="store-main",
        device_id="storage-cam-01",
        state_store=SnapshotStore(tmp_path / "state.json"),
    )


def test_mock_scene_produces_count_quality_and_valid_adp_events(tmp_path: Path) -> None:
    observations, events = build_pipeline(tmp_path).analyze(MODULE_ROOT / "data" / "mock_scene.json")
    lemon = next(item for item in observations if item.ingredient_id == "lemon")
    assert lemon.object_count == 4
    assert lemon.defective_count == 1
    assert lemon.review_count == 1
    assert lemon.physical_quantity == Decimal("480")
    assert lemon.defective_quantity == Decimal("120")
    assert {event["event_type"] for event in events} == {
        "vision.storage.detected",
        "inventory.detected",
        "quality.abnormal",
    }
    vision_event = next(event for event in events if event["event_type"] == "vision.storage.detected")
    assert vision_event["payload"]["location_id"] == "bar"
    assert {item["ingredient_id"] for item in vision_event["payload"]["detections"]} == {"lemon", "tomato"}

    schema = json.loads((REPO_ROOT / "contracts" / "adp" / "v1" / "envelope.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for event in events:
        validator.validate(event)


def test_unexplained_decrease_opens_alarm_but_authorized_task_suppresses_it(tmp_path: Path) -> None:
    pipeline = build_pipeline(tmp_path)
    source = MODULE_ROOT / "data" / "mock_scene.json"
    pipeline.analyze(source)
    scene = json.loads(source.read_text(encoding="utf-8"))
    scene["detections"] = scene["detections"][1:]
    reduced = tmp_path / "reduced.json"
    reduced.write_text(json.dumps(scene), encoding="utf-8")

    _, events = pipeline.analyze(reduced)
    assert any(
        event["event_type"] == "vision.storage.security"
        and event["payload"]["event_subtype"] == "unexplained_inventory_decrease"
        for event in events
    )

    pipeline.analyze(source)
    _, authorized_events = pipeline.analyze(reduced, authorized_task_ids=["task-001"])
    assert all(event["event_type"] != "vision.storage.security" for event in authorized_events)

