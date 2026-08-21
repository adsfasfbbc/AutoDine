from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer

from autodine_core.modules.inventory.models import InventoryPolicy


def _serialize_decimal(value: Decimal) -> str:
    normalized = format(value.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


class IngredientSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    ingredient_id: str
    name: str
    unit: str
    inventory_policy: InventoryPolicy


class InventorySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    store_id: str
    ingredient_id: str
    location_id: str
    physical_quantity: Decimal
    defective_quantity: Decimal
    reserved_quantity: Decimal
    reorder_threshold: Decimal
    available_quantity: Decimal

    @field_serializer(
        "physical_quantity",
        "defective_quantity",
        "reserved_quantity",
        "reorder_threshold",
        "available_quantity",
    )
    def serialize_decimal(self, value: Decimal) -> str:
        return _serialize_decimal(value)
