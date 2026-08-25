"""Smoke test for the front_vision service without a camera or GPU.

Generates a synthetic video file, runs the full service (capture loop +
pipeline + FastAPI) against stub detectors and a scripted fake sensor serial,
publishes into a real in-memory Core app, then asserts that valid ADP
envelopes arrived and that the fire event powered off the registered fan.

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
from fastapi.testclient import TestClient

# Make src/ importable when run as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
# Make the Core app importable (edge/front_vision/scripts -> repo root is 3 up).
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "apps" / "autodine_core" / "src"))

from front_vision.adp import AdpPublisher, validate_envelope  # noqa: E402
from front_vision.config import ENVELOPE_SCHEMA_PATH, FrontVisionConfig  # noqa: E402
from front_vision.pipeline import FrontVisionPipeline  # noqa: E402
from front_vision.safety_fusion import SafetyEngine  # noqa: E402

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


class FakeFireVision:
    """Stand-in for FireDetector: always 'sees' a flame at high confidence."""

    def analyze(self, frame):
        return 0.9, True


class FakeEnvSensor:
    """Stand-in for EnvSensorMonitor: scripted multi-register readings with
    flame + high temperature + high PM2.5 (rule A vote3 and rule B both hold)."""

    readings = {
        "tvoc": 100, "temperature": 60, "humidity": 50,
        "pm25": 300, "flame": 1, "light": 300, "co2": 800,
    }

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        pass


def run() -> int:
    from autodine_core.main import create_app as create_core_app
    from autodine_core.modules.device.models import DeviceCommand
    from sqlalchemy import select

    from front_vision.capture import FrameSource
    from front_vision.fire_fusion import FireEngine
    from front_vision.service import create_app

    received: list[dict] = []
    invalid: list[str] = []

    # Real Core on an in-memory sqlite DB stands in for the deployed service:
    # its pydantic payload validation is the strongest contract check we have.
    core_app = create_core_app(database_url="sqlite+pysqlite:///:memory:")
    core_app.state.metadata.create_all(core_app.state.engine)
    core_client = TestClient(core_app)

    class _HttpxShim:
        """Minimal httpx.Client look-alike that forwards to the Core app."""

        def post(self, url, json=None):
            try:
                validate_envelope(json, ENVELOPE_SCHEMA_PATH)
            except Exception as exc:  # noqa: BLE001
                invalid.append(f"{json.get('event_type')}: {exc}")
            received.append(json)
            resp = core_client.post("/api/v1/events", json=json)
            if resp.status_code != 200:
                invalid.append(f"{json.get('event_type')}: core HTTP {resp.status_code} {resp.text[:200]}")
            return resp

        def close(self):
            core_client.close()

    with tempfile.TemporaryDirectory() as tmp:
        video = make_synthetic_video(Path(tmp) / "synthetic.mp4")

        config = FrontVisionConfig()
        config.source = str(video)
        config.core_url = "http://fake-core"
        config.queue_heartbeat_seconds = 1.0
        config.smooth_window_seconds = 1.0
        config.infer_every_n_frames = 1

        # Register a fan at the store so the fire event must power it off.
        resp = core_client.post(
            "/api/v1/devices",
            json={"store_id": config.store_id, "device_id": "fan-01", "device_type": "fan"},
        )
        assert resp.status_code == 200, resp.text

        capture = FrameSource(source=config.source, width=config.frame_width, height=config.frame_height)
        publisher = AdpPublisher(
            core_url=config.core_url,
            schema_path=ENVELOPE_SCHEMA_PATH,
            retries=2,
            backoff_seconds=0.1,
            client=_HttpxShim(),
        )
        pipeline = FrontVisionPipeline(
            config, publisher, capture, FakeDetector(),
            SafetyEngine(config, publisher, simulate=True),
            fire=FireEngine(
                config, publisher,
                vision_detector=FakeFireVision(), sensor_monitor=FakeEnvSensor(),
            ),
        )
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
                safety_events = [e for e in received if e["event_type"] == "vision.front.safety"]
                severities = {e["severity"] for e in safety_events}
                # Simulated cues activate at ~5s and escalate past 10s; the
                # scripted fire readings trigger on the first inference frame.
                if (
                    "queue.updated" in event_types
                    and "vision.front.fire" in event_types
                    and {"warning", "critical"} <= severities
                ):
                    break
                time.sleep(0.5)

            metrics = client.get("/metrics").json()
            logger.info("metrics: %s", json.dumps(metrics))

        assert not invalid, f"invalid envelopes received: {invalid}"
        assert "queue.updated" in event_types, "no queue.updated event published"
        assert metrics["current_count"] == 1, f"expected count 1, got {metrics['current_count']}"

        queue_events = [e for e in received if e["event_type"] == "queue.updated"]
        assert queue_events[0]["payload"]["waiting_count"] == 1

        safety_events = [e for e in received if e["event_type"] == "vision.front.safety"]
        assert safety_events, "no vision.front.safety event published"
        assert safety_events[0]["severity"] == "warning"
        assert {"warning", "critical"} <= {e["severity"] for e in safety_events}, \
            "safety episode did not escalate to critical"
        payload = safety_events[0]["payload"]
        assert payload["event_subtype"] == "violent_interaction"
        assert payload["zone_id"] == "front-hall"
        assert payload["vision_score"] > 0 and payload["audio_score"] > 0

        fire_events = [e for e in received if e["event_type"] == "vision.front.fire"]
        assert fire_events, "no vision.front.fire event published"
        fire = fire_events[0]["payload"]
        assert fire["event_subtype"] == "flame_dual_confirm"
        assert fire["triggered_rule"] == "vote3"
        assert fire["vote_count"] >= 3
        assert set(fire["abnormal_channels"]) >= {"vision", "flame", "temperature", "pm25"}
        assert fire["readings"]["flame"] == 1

        # Device linkage: the registered fan must have been powered off (one
        # command per published fire event — warning plus the escalation).
        session = core_app.state.session_factory()
        commands = session.scalars(select(DeviceCommand)).all()
        assert commands, "no device.command created on fire"
        assert {c.device_id for c in commands} == {"fan-01"}
        assert len(commands) == len(fire_events)
        assert all(c.command_type == "power_off" for c in commands)
        assert all(c.parameters["reason"] == "fire_alarm" for c in commands)
        alarms = core_client.get(f"/api/v1/alarms?store_id={config.store_id}").json()["data"]["items"]
        fire_alarms = [a for a in alarms if a["source_key"].startswith("front_fire:")]
        assert fire_alarms, f"no front_fire alarm in core: {alarms}"
        session.close()

    logger.info("SMOKE OK: %d envelopes received (%s)", len(received), sorted(event_types))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
