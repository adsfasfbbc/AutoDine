"""Smoke test for the front_vision service without a camera or GPU.

Generates a synthetic video file, runs the full service (capture loop +
pipeline + FastAPI) against a stub detector and a local fake Core receiver,
then asserts that valid ADP envelopes were published.

Usage (from edge/front_vision/):
    .venv/Scripts/python scripts/smoke_front_vision.py
"""
from __future__ import annotations

import json
import logging
import sys
import tempfile
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

# Make src/ importable when run as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from front_vision.adp import AdpPublisher, validate_envelope  # noqa: E402
from front_vision.config import ENVELOPE_SCHEMA_PATH, FrontVisionConfig  # noqa: E402
from front_vision.pipeline import FrontVisionPipeline  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("smoke")


def make_synthetic_video(path: Path, frames: int = 90, size=(640, 480)) -> Path:
    """Write a synthetic clip: a moving 'person' blob and a static face-ish circle."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, 15.0, size)
    if not writer.isOpened():
        raise RuntimeError("could not open VideoWriter")
    for i in range(frames):
        frame = np.full((size[1], size[0], 3), 30, dtype=np.uint8)
        x = 50 + (i * 3) % (size[0] - 150)
        cv2.rectangle(frame, (x, 120), (x + 80, 400), (180, 180, 200), -1)  # body
        cv2.circle(frame, (x + 40, 90), 35, (150, 120, 110), -1)             # head
        writer.write(frame)
    writer.release()
    return path


class FakeDetector:
    """Stand-in for PersonDetector: reports a fixed person box in-frame."""

    backend_name = "fake"

    def detect_with_scores(self, frame):
        return [((100.0, 100.0, 220.0, 460.0), 0.95)]

    def detect(self, frame):
        return [b for b, _ in self.detect_with_scores(frame)]


def run() -> int:
    from front_vision.capture import FrameSource
    from front_vision.service import create_app

    received: list[dict] = []
    invalid: list[str] = []

    fake_core = FastAPI()

    @fake_core.post("/api/v1/events")
    async def ingest(request: Request) -> dict:
        body = await request.json()
        try:
            validate_envelope(body, ENVELOPE_SCHEMA_PATH)
            received.append(body)
        except Exception as exc:  # noqa: BLE001
            invalid.append(f"{body.get('event_type')}: {exc}")
        return {"status": "ok"}

    class _HttpxShim:
        """Minimal httpx.Client look-alike that forwards to the fake Core."""

        def __init__(self, core_app):
            self._client = TestClient(core_app)

        def post(self, url, json=None):
            return self._client.post("/api/v1/events", json=json)

        def close(self):
            self._client.close()

    with tempfile.TemporaryDirectory() as tmp:
        video = make_synthetic_video(Path(tmp) / "synthetic.mp4")

        config = FrontVisionConfig()
        config.source = str(video)
        config.core_url = "http://fake-core"
        config.queue_heartbeat_seconds = 1.0
        config.smooth_window_seconds = 1.0
        config.infer_every_n_frames = 1

        capture = FrameSource(source=config.source, width=config.frame_width, height=config.frame_height)
        publisher = AdpPublisher(
            core_url=config.core_url,
            schema_path=ENVELOPE_SCHEMA_PATH,
            retries=2,
            backoff_seconds=0.1,
            client=_HttpxShim(fake_core),
        )
        pipeline = FrontVisionPipeline(config, publisher, capture, FakeDetector())
        app = create_app(config, pipeline=pipeline, capture=capture)

        deadline = time.monotonic() + 30.0
        with TestClient(app) as client:
            health = client.get("/health").json()
            while not health["capture_alive"] and time.monotonic() < deadline:
                time.sleep(0.2)
                health = client.get("/health").json()
            logger.info("health: %s", json.dumps(health))
            assert health["capture_alive"], "capture did not deliver frames"

            event_types = set()
            while time.monotonic() < deadline:
                metrics = client.get("/metrics").json()
                event_types = {e["event_type"] for e in received}
                if "queue.updated" in event_types:
                    break
                time.sleep(0.5)

            metrics = client.get("/metrics").json()
            logger.info("metrics: %s", json.dumps(metrics))

        assert not invalid, f"invalid envelopes received: {invalid}"
        assert "queue.updated" in event_types, "no queue.updated event published"
        assert metrics["current_count"] == 1, f"expected count 1, got {metrics['current_count']}"

        queue_events = [e for e in received if e["event_type"] == "queue.updated"]
        assert queue_events[0]["payload"]["waiting_count"] == 1

    logger.info("SMOKE OK: %d envelopes received (%s)", len(received), sorted(event_types))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
