from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, Sequence

from .models import Detection


class VisionBackend(Protocol):
    name: str

    def detect(self, source: Path) -> Sequence[Detection]: ...


class MockBackend:
    """Loads stable detections so the complete integration works without a GPU."""

    name = "mock-v1"

    def detect(self, source: Path) -> Sequence[Detection]:
        raw = json.loads(source.read_text(encoding="utf-8"))
        return [
            Detection(
                ingredient_id=item["ingredient_id"],
                location_id=item["location_id"],
                confidence=float(item["confidence"]),
                quality_status=item.get("quality_status", "good"),
                quality_confidence=float(item.get("quality_confidence", 1.0)),
                bbox_xyxy=tuple(float(value) for value in item["bbox_xyxy"]),
            )
            for item in raw["detections"]
        ]


class BackendUnavailableError(RuntimeError):
    pass


def quality_status_from_label(label: str) -> str:
    normalized = label.lower().replace("_", " ").replace("-", " ")
    if label.lower().startswith("s_"):
        return "defective"
    if label.lower().startswith("f_"):
        return "good"
    if any(word in normalized for word in ("spoiled", "rotten", "defective", "non fresh")):
        return "defective"
    if "fresh" in normalized or "good" in normalized:
        return "good"
    return "review"


class CountGDPlusPlusBackend:
    """Declared adapter boundary for the separately installed official backend."""

    name = "countgd-plus-plus"

    def detect(self, source: Path) -> Sequence[Detection]:
        raise BackendUnavailableError(
            "CountGD++ is not vendored. Configure the official Linux/CUDA service "
            "and implement this adapter against its inference result before selecting it."
        )


class UltralyticsFruitBackend:
    """Runs real YOLO fruit detection and optional crop-level quality classification."""

    name = "ultralytics-yolo"

    def __init__(
        self,
        detector_path: str,
        *,
        quality_model_path: str | None = None,
        location_id: str = "storage-main",
        confidence: float = 0.35,
    ) -> None:
        import torch
        from ultralytics import YOLO

        self.detector = YOLO(detector_path)
        self.quality_model = YOLO(quality_model_path) if quality_model_path else None
        self.location_id = location_id
        self.confidence = confidence
        self.device = 0 if torch.cuda.is_available() else "cpu"

    def detect(self, source: Path) -> Sequence[Detection]:
        result = self.detector.predict(
            source=str(source),
            conf=self.confidence,
            device=self.device,
            verbose=False,
        )[0]
        if result.boxes is None:
            return []

        image = result.orig_img
        detections: list[Detection] = []
        for box, class_id, detection_confidence in zip(
            result.boxes.xyxy.cpu().tolist(),
            result.boxes.cls.cpu().tolist(),
            result.boxes.conf.cpu().tolist(),
        ):
            detector_label = str(result.names[int(class_id)]).lower()
            if detector_label not in {"apple", "banana", "orange"}:
                continue
            x1, y1, x2, y2 = (int(value) for value in box)
            quality_status = "review"
            quality_confidence = 0.0
            if self.quality_model is not None:
                quality_result = self.quality_model.predict(
                    source=image[y1:y2, x1:x2],
                    device=self.device,
                    verbose=False,
                )[0]
                top1 = int(quality_result.probs.top1)
                quality_status = quality_status_from_label(str(quality_result.names[top1]))
                quality_confidence = float(quality_result.probs.top1conf.cpu())
            detections.append(
                Detection(
                    ingredient_id=detector_label,
                    location_id=self.location_id,
                    confidence=float(detection_confidence),
                    quality_status=quality_status,
                    quality_confidence=quality_confidence,
                    bbox_xyxy=tuple(float(value) for value in box),
                )
            )
        return detections

