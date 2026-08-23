from __future__ import annotations

from smart_storage_vision.security import PersonDetection, evaluate_security, make_unauthorized_entry_event
from smart_storage_vision.backends import UltralyticsFruitBackend


def test_quality_labels_are_mapped_without_claiming_unknown_as_good() -> None:
    assert UltralyticsFruitBackend._quality("F_Lemon") == "good"
    assert UltralyticsFruitBackend._quality("S_Lemon") == "defective"
    assert UltralyticsFruitBackend._quality("fresh_banana") == "good"
    assert UltralyticsFruitBackend._quality("spoiled-orange") == "defective"
    assert UltralyticsFruitBackend._quality("banana") == "review"


def test_person_in_open_door_without_authorization_emits_security_event() -> None:
    observation = evaluate_security(
        [PersonDetection(confidence=0.91, bbox_xyxy_normalized=(0.4, 0.2, 0.6, 0.9))],
        doorway_roi=(0.25, 0.0, 0.75, 1.0),
        door_open=True,
        authorization_present=False,
        zone_id="storage-door",
    )
    event = make_unauthorized_entry_event(
        observation,
        trace_id="security-test",
        store_id="store-main",
        device_id="storage-cam-01",
    )
    assert observation.person_count == 1
    assert observation.unauthorized_entry is True
    assert event is not None
    assert event["event_type"] == "vision.storage.security"
    assert event["payload"]["event_subtype"] == "unauthorized_entry"


def test_authorized_person_does_not_emit_security_event() -> None:
    observation = evaluate_security(
        [PersonDetection(confidence=0.91, bbox_xyxy_normalized=(0.4, 0.2, 0.6, 0.9))],
        doorway_roi=(0.25, 0.0, 0.75, 1.0),
        door_open=True,
        authorization_present=True,
        zone_id="storage-door",
    )
    assert make_unauthorized_entry_event(
        observation,
        trace_id="security-test",
        store_id="store-main",
        device_id="storage-cam-01",
    ) is None
