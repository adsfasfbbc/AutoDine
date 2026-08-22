"""ADP v1.0 envelope construction, local schema validation and publishing.

Every event emitted by front_vision is wrapped in the shared ADP envelope,
validated against contracts/adp/v1/envelope.schema.json before sending, and
POSTed to the Core /api/v1/events endpoint with bounded retries.
"""
from __future__ import annotations

import json
import logging
import queue
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger("front_vision.adp")

_SCHEMA_CACHE: dict[Path, dict] = {}
_SCHEMA_LOCK = threading.Lock()


def load_envelope_schema(schema_path: Path) -> dict:
    """Load (and cache) the local ADP envelope JSON schema."""
    with _SCHEMA_LOCK:
        if schema_path not in _SCHEMA_CACHE:
            _SCHEMA_CACHE[schema_path] = json.loads(Path(schema_path).read_text(encoding="utf-8"))
        return _SCHEMA_CACHE[schema_path]


def build_envelope(
    *,
    event_type: str,
    payload: dict,
    store_id: str,
    module: str = "front_vision",
    device_id: Optional[str] = None,
    severity: str = "info",
    trace_id: Optional[str] = None,
) -> dict:
    """Build an ADP v1.0 envelope dict (all snake_case, per contract)."""
    envelope: dict[str, Any] = {
        "protocol": "ADP",
        "version": "1.0",
        "event_id": f"evt-{uuid.uuid4().hex}",
        "trace_id": trace_id or f"tr-{uuid.uuid4().hex}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "store_id": store_id,
        "source": {"module": module},
        "event_type": event_type,
        "severity": severity,
        "payload": payload,
    }
    if device_id:
        envelope["source"]["device_id"] = device_id
    return envelope


def validate_envelope(envelope: dict, schema_path: Path) -> None:
    """Validate an envelope against the local contract; raise on violation."""
    from jsonschema import validate

    validate(instance=envelope, schema=load_envelope_schema(schema_path))


class AdpPublisher:
    """Publishes validated ADP envelopes to the Core event endpoint.

    `publish` blocks with retries; `enqueue` hands the event to a background
    worker thread so Core outages never stall the inference loop.
    """

    def __init__(
        self,
        *,
        core_url: str,
        schema_path: Path,
        retries: int = 3,
        backoff_seconds: float = 0.5,
        timeout_seconds: float = 5.0,
        client: Optional[httpx.Client] = None,
        queue_size: int = 256,
    ) -> None:
        self._endpoint = core_url.rstrip("/") + "/api/v1/events"
        self._schema_path = schema_path
        self._retries = max(1, retries)
        self._backoff = backoff_seconds
        self._timeout = timeout_seconds
        # trust_env=False: ignore system proxy env vars; Core is on localhost and
        # a SOCKS proxy would also require the optional socksio package.
        self._client = client or httpx.Client(timeout=timeout_seconds, trust_env=False)
        self._queue: "queue.Queue[Optional[dict]]" = queue.Queue(maxsize=queue_size)
        self._worker: Optional[threading.Thread] = None
        self.dropped_events = 0

    @property
    def endpoint(self) -> str:
        return self._endpoint

    # -- async publishing ---------------------------------------------------
    def start_worker(self) -> None:
        if self._worker is None:
            self._worker = threading.Thread(target=self._drain, name="adp-publisher", daemon=True)
            self._worker.start()

    def enqueue(self, **kwargs) -> None:
        """Queue an event for background publishing (drops oldest if full)."""
        try:
            self._queue.put_nowait(kwargs)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            self.dropped_events += 1
            try:
                self._queue.put_nowait(kwargs)
            except queue.Full:
                pass

    def _drain(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            try:
                self.publish(**item)
            except Exception:
                logger.exception("background publish crashed for %s", item.get("event_type"))

    def publish(
        self,
        *,
        event_type: str,
        payload: dict,
        store_id: str,
        device_id: Optional[str] = None,
        severity: str = "info",
        trace_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Build, validate and POST an envelope. Returns the envelope or None on failure."""
        envelope = build_envelope(
            event_type=event_type,
            payload=payload,
            store_id=store_id,
            device_id=device_id,
            severity=severity,
            trace_id=trace_id,
        )
        try:
            validate_envelope(envelope, self._schema_path)
        except Exception:
            logger.exception("envelope failed local schema validation; event dropped: %s", event_type)
            return None

        attempt = 0
        while attempt < self._retries:
            attempt += 1
            try:
                resp = self._client.post(self._endpoint, json=envelope)
                if resp.is_success:
                    logger.info("published %s (%s) -> %s", event_type, envelope["event_id"], resp.status_code)
                    return envelope
                logger.warning(
                    "publish %s attempt %d/%d got HTTP %s: %s",
                    event_type, attempt, self._retries, resp.status_code, resp.text[:200],
                )
            except httpx.HTTPError as exc:
                logger.warning("publish %s attempt %d/%d failed: %s", event_type, attempt, self._retries, exc)
            if attempt < self._retries:
                time.sleep(self._backoff * (2 ** (attempt - 1)))
        logger.error("giving up publishing %s (%s) after %d attempts", event_type, envelope["event_id"], self._retries)
        return None

    def close(self) -> None:
        if self._worker is not None:
            self._queue.put(None)
            self._worker.join(timeout=5.0)
            self._worker = None
        self._client.close()
