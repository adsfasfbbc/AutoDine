from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from statistics import fmean
from typing import Sequence
from uuid import uuid4

from .backends import VisionBackend
from .events import decimal_text, make_event
from .models import IngredientCalibration, InventoryObservation
from .state import SnapshotStore


class SmartStoragePipeline:
    def __init__(
        self,
        *,
        backend: VisionBackend,
        calibrations: Sequence[IngredientCalibration],
        store_id: str,
        device_id: str,
        state_store: SnapshotStore | None = None,
        detection_threshold: float = 0.5,
        quality_threshold: float = 0.7,
    ) -> None:
        self.backend = backend
        self.calibrations = {item.ingredient_id: item for item in calibrations}
        self.store_id = store_id
        self.device_id = device_id
        self.state_store = state_store
        self.detection_threshold = detection_threshold
        self.quality_threshold = quality_threshold

    def analyze(
        self,
        source: Path,
        *,
        authorized_task_ids: Sequence[str] = (),
    ) -> tuple[list[InventoryObservation], list[dict]]:
        detections = [d for d in self.backend.detect(source) if d.confidence >= self.detection_threshold]
        grouped: dict[tuple[str, str], list] = defaultdict(list)
        for detection in detections:
            if detection.ingredient_id not in self.calibrations:
                raise ValueError(f"missing calibration for {detection.ingredient_id}")
            grouped[(detection.ingredient_id, detection.location_id)].append(detection)

        observations: list[InventoryObservation] = []
        for (ingredient_id, location_id), items in sorted(grouped.items()):
            calibration = self.calibrations[ingredient_id]
            defective = [
                item
                for item in items
                if item.quality_status == "defective" and item.quality_confidence >= self.quality_threshold
            ]
            review = [
                item
                for item in items
                if item.quality_status == "review" or item.quality_confidence < self.quality_threshold
            ]
            observations.append(
                InventoryObservation(
                    ingredient_id=ingredient_id,
                    location_id=location_id,
                    unit=calibration.unit,
                    object_count=len(items),
                    defective_count=len(defective),
                    review_count=len(review),
                    physical_quantity=calibration.quantity_per_detection * len(items),
                    defective_quantity=calibration.quantity_per_detection * len(defective),
                    mean_confidence=fmean(item.confidence for item in items),
                )
            )

        trace_id = "vision-a-" + uuid4().hex
        events = [self._diagnostic_event(observations, trace_id)]
        previous = self.state_store.load() if self.state_store else {"observations": {}}
        previous_values = previous.get("observations", {})

        for observation in observations:
            events.append(self._inventory_event(observation, trace_id))
            if observation.defective_quantity > 0:
                events.append(self._quality_event(observation, trace_id))
            key = f"{observation.location_id}:{observation.ingredient_id}"
            old_value = Decimal(str(previous_values.get(key, observation.physical_quantity)))
            if observation.physical_quantity < old_value and not authorized_task_ids:
                events.append(self._loss_alarm(observation, old_value, trace_id))

        if self.state_store:
            self.state_store.save(
                {
                    "observations": {
                        f"{item.location_id}:{item.ingredient_id}": decimal_text(item.physical_quantity)
                        for item in observations
                    },
                    "authorized_task_ids": list(authorized_task_ids),
                    "trace_id": trace_id,
                }
            )
        return observations, events

    def _diagnostic_event(self, observations: Sequence[InventoryObservation], trace_id: str) -> dict:
        return make_event(
            event_type="vision.storage.detected",
            trace_id=trace_id,
            store_id=self.store_id,
            device_id=self.device_id,
            payload={
                "backend": self.backend.name,
                "observations": [
                    {
                        "ingredient_id": item.ingredient_id,
                        "location_id": item.location_id,
                        "object_count": item.object_count,
                        "defective_count": item.defective_count,
                        "review_count": item.review_count,
                        "mean_confidence": round(item.mean_confidence, 4),
                    }
                    for item in observations
                ],
            },
        )

    def _inventory_event(self, item: InventoryObservation, trace_id: str) -> dict:
        return make_event(
            event_type="inventory.detected",
            trace_id=trace_id,
            store_id=self.store_id,
            device_id=self.device_id,
            payload={
                "ingredient_id": item.ingredient_id,
                "location_id": item.location_id,
                "physical_quantity": decimal_text(item.physical_quantity),
                "unit": item.unit,
                "defective_quantity": decimal_text(item.defective_quantity),
            },
        )

    def _quality_event(self, item: InventoryObservation, trace_id: str) -> dict:
        return make_event(
            event_type="quality.abnormal",
            trace_id=trace_id,
            store_id=self.store_id,
            device_id=self.device_id,
            severity="warning",
            payload={
                "ingredient_id": item.ingredient_id,
                "location_id": item.location_id,
                "defective_quantity": decimal_text(item.defective_quantity),
            },
        )

    def _loss_alarm(self, item: InventoryObservation, old_value: Decimal, trace_id: str) -> dict:
        return make_event(
            event_type="alarm.opened",
            trace_id=trace_id,
            store_id=self.store_id,
            device_id=self.device_id,
            severity="warning",
            payload={
                "alarm_type": "unexplained_inventory_decrease",
                "ingredient_id": item.ingredient_id,
                "location_id": item.location_id,
                "previous_physical_quantity": decimal_text(old_value),
                "current_physical_quantity": decimal_text(item.physical_quantity),
                "decrease_quantity": decimal_text(old_value - item.physical_quantity),
                "unit": item.unit,
                "authorized_task_ids": [],
            },
        )

