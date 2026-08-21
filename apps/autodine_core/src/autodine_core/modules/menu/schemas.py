from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer

from autodine_core.modules.inventory.schemas import _serialize_decimal
from autodine_core.modules.menu.models import ProductStatus


class ProductSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    product_id: str
    name: str
    price: Decimal
    status: ProductStatus
    available_product_quantity: int

    @field_serializer("price")
    def serialize_price(self, value: Decimal) -> str:
        return _serialize_decimal(value)
