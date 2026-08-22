from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

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


class VisionStorageDetectionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingredient_id: str
    quantity: Decimal
    unit: str
    confidence: float = Field(ge=0.0, le=1.0)


class VisionStorageDetectedPayloadSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: str
    detections: List[VisionStorageDetectionSchema] = Field(min_length=1)


class QueueUpdatedPayloadSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone_id: str = Field(min_length=1)
    waiting_count: int = Field(ge=0)
    estimated_wait_seconds: Optional[int] = Field(default=None, ge=0)


class CustomerExperienceSummaryPayloadSchema(BaseModel):
    """Anonymous aggregate expression ratios from front vision; no face data."""

    model_config = ConfigDict(extra="forbid")

    sample_count: int = Field(ge=0)
    positive_ratio: float = Field(ge=0.0, le=1.0)
    neutral_ratio: float = Field(ge=0.0, le=1.0)
    negative_ratio: float = Field(ge=0.0, le=1.0)


class DeviceCommandResultPayloadSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: str = Field(min_length=1)
    status: str = Field(pattern=r"^(SUCCEEDED|FAILED|TIMED_OUT)$")
    result: Dict[str, Any] = Field(default_factory=dict)


class AdpEventEnvelopeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: str
    version: str
    event_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    trace_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    event_type: str = Field(
        pattern=r"^(vision\.storage|vision\.front|inventory|quality|menu|order|production|device|robot|alarm|queue|customer)\.[a-z0-9]+(?:_[a-z0-9]+)*(?:\.[a-z0-9]+(?:_[a-z0-9]+)*)*$"
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
        if event_type == "vision.storage.detected":
            return VisionStorageDetectedPayloadSchema.model_validate(value).model_dump()
        if event_type == "quality.abnormal":
            return QualityAbnormalPayloadSchema.model_validate(value).model_dump(exclude_none=True)
        if event_type == "queue.updated":
            return QueueUpdatedPayloadSchema.model_validate(value).model_dump(exclude_none=True)
        if event_type == "customer.experience_summary":
            return CustomerExperienceSummaryPayloadSchema.model_validate(value).model_dump()
        if event_type == "device.command_result":
            return DeviceCommandResultPayloadSchema.model_validate(value).model_dump()
        return value
