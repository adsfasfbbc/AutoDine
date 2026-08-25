from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .events import make_event


@dataclass(frozen=True)
class PersonDetection:
    confidence: float
    bbox_xyxy_normalized: tuple[float, float, float, float]


@dataclass(frozen=True)
class SecurityObservation:
    person_count: int
    confidence: float
    door_open: bool
    authorization_present: bool
    unauthorized_entry: bool
    zone_id: str

    def to_dict(self) -> dict:
        return asdict(self)


class UltralyticsPersonDetector:
    """Runs a real YOLO person-class inference on an image or video frame."""

    def __init__(self, model_path: str, confidence: float = 0.4) -> None:
        import torch
        from ultralytics import YOLO

        self.model = YOLO(model_path)
        self.confidence = confidence
        self.device = 0 if torch.cuda.is_available() else "cpu"

    def detect(self, source: Path) -> list[PersonDetection]:
        result = self.model.predict(
            source=str(source),
            classes=[0],
            conf=self.confidence,
            device=self.device,
            verbose=False,
        )[0]
        height, width = result.orig_shape
        if result.boxes is None:
            return []
        boxes = result.boxes.xyxy.cpu().tolist()
        confidences = result.boxes.conf.cpu().tolist()
        return [
            PersonDetection(
                confidence=float(confidence),
                bbox_xyxy_normalized=(x1 / width, y1 / height, x2 / width, y2 / height),
            )
            for (x1, y1, x2, y2), confidence in zip(boxes, confidences)
        ]


def evaluate_security(
    detections: list[PersonDetection],
    *,
    doorway_roi: tuple[float, float, float, float],
    door_open: bool,
    authorization_present: bool,
    zone_id: str,
) -> SecurityObservation:
    x1, y1, x2, y2 = doorway_roi
    people_in_doorway = []
    for detection in detections:
        bx1, by1, bx2, by2 = detection.bbox_xyxy_normalized
        center_x = (bx1 + bx2) / 2
        center_y = (by1 + by2) / 2
        if x1 <= center_x <= x2 and y1 <= center_y <= y2:
            people_in_doorway.append(detection)
    confidence = max((item.confidence for item in people_in_doorway), default=0.0)
    unauthorized = bool(people_in_doorway) and door_open and not authorization_present
    return SecurityObservation(
        person_count=len(people_in_doorway),
        confidence=confidence,
        door_open=door_open,
        authorization_present=authorization_present,
        unauthorized_entry=unauthorized,
        zone_id=zone_id,
    )


def make_unauthorized_entry_event(
    observation: SecurityObservation,
    *,
    trace_id: str,
    store_id: str,
    device_id: str,
) -> dict | None:
    if not observation.unauthorized_entry:
        return None
    return make_event(
        event_type="vision.storage.security",
        trace_id=trace_id,
        store_id=store_id,
        device_id=device_id,
        severity="critical",
        payload={
            "event_subtype": "unauthorized_entry",
            "confidence": round(observation.confidence, 4),
            "person_count": observation.person_count,
            "door_open": observation.door_open,
            "authorization_present": observation.authorization_present,
            "zone_id": observation.zone_id,
        },
    )
