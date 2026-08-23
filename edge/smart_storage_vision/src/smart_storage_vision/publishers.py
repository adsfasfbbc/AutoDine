from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


CORE_EVENT_TYPES = {"inventory.detected", "quality.abnormal", "vision.storage.security"}


def write_events(events: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")


def publish_to_core(events: list[dict], core_url: str) -> list[dict]:
    results = []
    for event in events:
        if event["event_type"] not in CORE_EVENT_TYPES:
            continue
        body = json.dumps(event).encode("utf-8")
        request = Request(
            core_url.rstrip("/") + "/api/v1/events",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=5) as response:
                results.append(json.loads(response.read().decode("utf-8")))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Core rejected {event['event_type']}: {exc.code} {detail}") from exc
    return results

