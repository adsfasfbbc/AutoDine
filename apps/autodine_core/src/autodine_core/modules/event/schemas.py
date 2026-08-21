from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator


class EventSourceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_.-]*$")
    device_id: Optional[str] = None


class InventoryDetectedPayloadSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingredient_id: str
    location_id: str
    physical_quantity: Decimal
    unit: str
    defective_quantity: Optional[Decimal] = None
    reserved_quantity: Optional[Decimal] = None
    store_id: Optional[str] = None


class QualityAbnormalPayloadSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingredient_id: str
    location_id: str
    defective_quantity: Optional[Decimal] = None
    quantity: Optional[Decimal] = None

    @model_validator(mode="after")
    def validate_quantity_fields(self) -> "QualityAbnormalPayloadSchema":
        if self.defective_quantity is None and self.quantity is None:
            raise ValueError("defective_quantity or quantity is required")
        return self


class AdpEventEnvelopeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: str
    version: str
    event_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    trace_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    event_type: str = Field(
        pattern=r"^(vision\.storage|vision\.front|inventory|quality|menu|order|production|device|robot|alarm|queue)\.[a-z0-9]+(?:_[a-z0-9]+)*(?:\.[a-z0-9]+(?:_[a-z0-9]+)*)*$"
    )
    severity: str = Field(pattern=r"^(debug|info|warning|error|critical)$")
    timestamp: datetime
    store_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    source: EventSourceSchema
    payload: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("protocol")
    @classmethod
    def validate_protocol(cls, value: str) -> str:
        if value != "ADP":
            raise ValueError("protocol must be ADP")
        return value

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if value != "1.0":
            raise ValueError("version must be 1.0")
        return value

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, value: Dict[str, Any], info: ValidationInfo) -> Dict[str, Any]:
        event_type = info.data.get("event_type")
        if event_type == "inventory.detected":
            return InventoryDetectedPayloadSchema.model_validate(value).model_dump()
        if event_type == "quality.abnormal":
            return QualityAbnormalPayloadSchema.model_validate(value).model_dump(exclude_none=True)
        return value
