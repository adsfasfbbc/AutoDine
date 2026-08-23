"""Tests for the fire chain: flame sensor polling, vision throttle, fusion.

All tests are synthetic — no serial port, camera, GPU or model files.
"""
from __future__ import annotations

import time

import numpy as np
import pytest

from front_vision.adp import build_envelope, validate_envelope
from front_vision.config import ENVELOPE_SCHEMA_PATH, FrontVisionConfig
from front_vision.fire_fusion import EVENT_TYPE, FireEngine, FireFusion
from front_vision.fire_sensor import FlameSensorMonitor, default_sensor_port, parse_fire_register


# --- Modbus reply decoding ----------------------------------------------------

def _reply(state: int) -> bytes:
    """Minimal 7-byte reply whose flame register (hex chars 6:10) is `state`."""
    return bytes.fromhex("02 03 02") + state.to_bytes(2, "big") + b"\x00\x00"


def test_parse_fire_register_detects_flame() -> None:
    assert parse_fire_register(_reply(1)) == 1
    assert parse_fire_register(_reply(0)) == 0


def test_parse_fire_register_rejects_short_reply() -> None:
    assert parse_fire_register(b"\x02\x03") is None
    assert parse_fire_register(b"") is None


def test_default_sensor_port_is_platform_specific() -> None:
    port = default_sensor_port()
    assert isinstance(port, str) and port


# --- sensor monitor (fake serial) ----------------------------------------------

class _FakeSerial:
    """pyserial look-alike replaying a scripted sequence of replies."""

    def __init__(self, replies):
        self._replies = list(replies)
        self.writes: list[bytes] = []
        self.closed = False

    def reset_input_buffer(self) -> None:
        pass

    def reset_output_buffer(self) -> None:
        pass

    def write(self, data: bytes) -> int:
        self.writes.append(bytes(data))
        return len(data)

    def read(self, n: int) -> bytes:
        if self._replies:
            return self._replies.pop(0)
        return _reply(0)

    def close(self) -> None:
        self.closed = True


def test_sensor_monitor_polls_and_detects_flame() -> None:
    fake = _FakeSerial([_reply(0), _reply(1)])
    monitor = FlameSensorMonitor(
        port="COM-fake", poll_seconds=0.01, serial_factory=lambda: fake
    )
    assert monitor.start() is True
    try:
        deadline = time.monotonic() + 2.0
        while not monitor.flame_detected and time.monotonic() < deadline:
            time.sleep(0.01)
        assert monitor.flame_detected is True
        assert monitor.sensor_state == 1
        assert fake.writes, "sensor was never queried"
    finally:
        monitor.stop()
    assert fake.closed is True
    assert monitor.available is False


def test_sensor_monitor_open_failure_degrades_gracefully() -> None:
    def _broken():
        raise OSError("no such port")

    monitor = FlameSensorMonitor(port="COM-missing", serial_factory=_broken)
    assert monitor.start() is False   # degraded, no exception
    assert monitor.flame_detected is False
    assert monitor.available is False
    monitor.stop()  # must not raise


def test_sensor_monitor_short_reply_keeps_previous_state() -> None:
    fake = _FakeSerial([b"\x02\x03", _reply(1)])
    monitor = FlameSensorMonitor(port="COM-fake", poll_seconds=0.01, serial_factory=lambda: fake)
    monitor._ser = fake  # drive poll_once directly, without the polling thread
    assert monitor.poll_once() is None
    assert monitor.flame_detected is False
    assert monitor.poll_once() == 1


# --- fusion --------------------------------------------------------------------

class _FakePublisher:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def enqueue(self, **kwargs) -> None:
        self.events.append(kwargs)


def _fusion() -> tuple:
    pub = _FakePublisher()
    fusion = FireFusion(pub, store_id="store-main", device_id="front-cam-01", zone_id="front-hall")
    return fusion, pub


def _step(fusion: FireFusion, *, v: bool, s: bool, now: float, vc: float = 0.85):
    return fusion.update(vision_flag=v, vision_conf=vc, sensor_flag=s, sensor_state=1 if s else 0, now=now)


def test_fusion_single_channel_never_publishes() -> None:
    # Only vision ever fires.
    fusion, pub = _fusion()
    for t in (0.0, 1.0, 2.0):
        assert _step(fusion, v=True, s=False, now=t) is None
    assert pub.events == []
    # Only the sensor ever fires.
    fusion, pub = _fusion()
    for t in (0.0, 1.0, 2.0):
        assert _step(fusion, v=False, s=True, now=t) is None
    assert pub.events == []


def test_fusion_stale_single_channel_does_not_fuse() -> None:
    # Vision fired 4s ago — outside the ±3s window when the sensor fires.
    fusion, pub = _fusion()
    assert _step(fusion, v=True, s=False, now=0.0) is None
    assert _step(fusion, v=False, s=True, now=4.0) is None
    assert pub.events == []


def test_fusion_dual_channel_publishes_warning() -> None:
    fusion, pub = _fusion()
    payload = _step(fusion, v=True, s=True, now=0.0)
    assert payload is not None
    assert payload["event_subtype"] == "flame_dual_confirm"
    assert payload["zone_id"] == "front-hall"
    assert payload["vision_conf"] == 0.85
    assert payload["confidence"] == 0.85
    assert payload["sensor_state"] == 1
    assert payload["duration_ms"] == 0
    assert len(pub.events) == 1
    event = pub.events[0]
    assert event["event_type"] == EVENT_TYPE == "vision.front.fire"
    assert event["severity"] == "warning"


def test_fusion_offset_within_window_still_fuses() -> None:
    fusion, pub = _fusion()
    assert _step(fusion, v=True, s=False, now=0.0) is None
    payload = _step(fusion, v=False, s=True, now=2.0)   # ±3s window
    assert payload is not None
    assert len(pub.events) == 1


def test_fusion_cooldown_dedupes_repeat_warnings() -> None:
    fusion, pub = _fusion()
    assert _step(fusion, v=True, s=True, now=0.0) is not None
    assert _step(fusion, v=True, s=True, now=5.0) is None   # same episode, <10s
    assert len(pub.events) == 1


def test_fusion_sustained_episode_escalates_to_critical() -> None:
    fusion, pub = _fusion()
    assert _step(fusion, v=True, s=True, now=0.0)["duration_ms"] == 0
    payload = _step(fusion, v=True, s=True, now=11.0)       # >10s sustained
    assert payload is not None
    assert payload["duration_ms"] == 11000
    assert pub.events[-1]["severity"] == "critical"
    assert len(pub.events) == 2
    assert _step(fusion, v=True, s=True, now=12.0) is None  # escalate once


def test_fusion_retrigger_during_cooldown_is_critical() -> None:
    fusion, pub = _fusion()
    _step(fusion, v=True, s=True, now=0.0)
    _step(fusion, v=False, s=False, now=4.0)                # episode ends (stale)
    payload = _step(fusion, v=True, s=True, now=10.0)       # re-trigger inside 30s cooldown
    assert payload is not None
    assert pub.events[-1]["severity"] == "critical"
    assert len(pub.events) == 2


def test_fusion_after_cooldown_publishes_warning_again() -> None:
    fusion, pub = _fusion()
    _step(fusion, v=True, s=True, now=0.0)
    _step(fusion, v=False, s=False, now=4.0)
    payload = _step(fusion, v=True, s=True, now=35.0)       # cooldown expired
    assert payload is not None
    assert pub.events[-1]["severity"] == "warning"
    assert len(pub.events) == 2


def test_fire_envelope_passes_local_schema() -> None:
    fusion, pub = _fusion()
    _step(fusion, v=True, s=True, now=0.0)
    envelope = build_envelope(**pub.events[0])
    validate_envelope(envelope, ENVELOPE_SCHEMA_PATH)


# --- engine throttling (fake detector + fake sensor) ----------------------------

class _FakeVision:
    def __init__(self) -> None:
        self.calls = 0

    def analyze(self, frame):
        self.calls += 1
        return 0.9, True


class _FakeSensor:
    flame_detected = True
    sensor_state = 1

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        pass


def test_engine_throttles_vision_and_fuses_dual_channels() -> None:
    config = FrontVisionConfig()
    config.fire_infer_every_n_frames = 3
    pub = _FakePublisher()
    vision = _FakeVision()
    engine = FireEngine(config, pub, vision_detector=vision, sensor_monitor=_FakeSensor())

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    payload = None
    for i in range(5):
        payload = engine.update(frame, now=float(i) * 0.1) or payload

    # Frames 1 and 4 ran inference; frames 2, 3, 5 reused the cached result.
    assert vision.calls == 2
    # Cached vision flag still fuses with the live sensor state.
    assert payload is not None
    assert payload["event_subtype"] == "flame_dual_confirm"
    assert pub.events and pub.events[0]["event_type"] == "vision.front.fire"


def test_engine_without_sensor_never_publishes() -> None:
    config = FrontVisionConfig()
    pub = _FakePublisher()
    engine = FireEngine(config, pub, vision_detector=_FakeVision(), sensor_monitor=None)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    for i in range(3):
        assert engine.update(frame, now=float(i) * 0.1) is None
    assert pub.events == []
