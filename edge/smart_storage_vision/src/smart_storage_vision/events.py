from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4


def decimal_text(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def make_event(
    *,
    event_type: str,
    payload: dict[str, Any],
    trace_id: str,
    store_id: str,
    device_id: str,
    severity: str = "info",
) -> dict[str, Any]:
    namespace = event_type.replace(".", "-")
    return {
        "protocol": "ADP",
        "version": "1.0",
        "event_id": f"a-{namespace}-{uuid4().hex}",
        "trace_id": trace_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "store_id": store_id,
        "source": {"module": "smart_storage_vision", "device_id": device_id},
        "event_type": event_type,
        "severity": severity,
        "payload": payload,
    }

