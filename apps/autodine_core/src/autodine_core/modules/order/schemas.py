from __future__ import annotations

from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrderItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(min_length=1, max_length=64)
    quantity: int = Field(gt=0, le=100)


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: str = Field(min_length=1, max_length=64)
    customer_id: Optional[str] = Field(default=None, max_length=64)
    idempotency_key: str = Field(min_length=1, max_length=128)
    items: List[OrderItemCreate] = Field(min_length=1, max_length=50)

    @field_validator("items")
    @classmethod
    def validate_unique_products(cls, value: List[OrderItemCreate]) -> List[OrderItemCreate]:
        product_ids = [item.product_id for item in value]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("items must contain unique products")
        return value


class ActualConsumption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingredient_id: str = Field(min_length=1, max_length=64)
    location_id: str = Field(min_length=1, max_length=64)
    quantity: Decimal = Field(gt=0)


class CompleteTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actual_consumption: List[ActualConsumption] = Field(default_factory=list)

