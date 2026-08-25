from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field


class DeviceCommandCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: str = Field(min_length=1)
    command_type: str = Field(min_length=1)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class DeviceRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    device_type: str = Field(min_length=1)
