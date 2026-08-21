from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AlarmOpenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    severity: str = Field(pattern=r"^(info|warning|error|critical)$")
    message: str = Field(min_length=1)
