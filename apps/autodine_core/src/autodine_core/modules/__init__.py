from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def response_envelope(data: Any, *, code: int = 0, message: str = "success") -> Dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "request_id": uuid4().hex,
        "timestamp": utc_timestamp(),
        "data": data,
    }
