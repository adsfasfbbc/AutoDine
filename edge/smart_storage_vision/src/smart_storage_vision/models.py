from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


QualityStatus = Literal["good", "defective", "review"]


@dataclass(frozen=True)
class Detection:
    ingredient_id: str
    location_id: str
    confidence: float
    quality_status: QualityStatus
    quality_confidence: float
    bbox_xyxy: tuple[float, float, float, float]


@dataclass(frozen=True)
class IngredientCalibration:
    ingredient_id: str
    unit: str
    quantity_per_detection: Decimal


@dataclass(frozen=True)
class InventoryObservation:
    ingredient_id: str
    location_id: str
    unit: str
    object_count: int
    defective_count: int
    review_count: int
    physical_quantity: Decimal
    defective_quantity: Decimal
    mean_confidence: float

