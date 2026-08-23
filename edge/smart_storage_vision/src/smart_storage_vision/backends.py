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


class CountGDPlusPlusBackend:
    """Declared adapter boundary for the separately installed official backend."""

    name = "countgd-plus-plus"

    def detect(self, source: Path) -> Sequence[Detection]:
        raise BackendUnavailableError(
            "CountGD++ is not vendored. Configure the official Linux/CUDA service "
            "and implement this adapter against its inference result before selecting it."
        )

