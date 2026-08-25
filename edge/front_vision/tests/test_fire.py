"""Tests for the fire chain: env sensor polling, vision throttle, 8-channel
voting fusion.

All tests are synthetic — no serial port, camera, GPU or model files.
"""
from __future__ import annotations

import time

import numpy as np
import pytest

from front_vision.adp import build_envelope, validate_envelope
from front_vision.config import ENVELOPE_SCHEMA_PATH, FrontVisionConfig
from front_vision.env_sensor import (
    REGISTERS,
    EnvSensorMonitor,
    build_query,
    calc_crc16,
    default_sensor_port,
    parse_register_reply,
)
from front_vision.fire_fusion import EVENT_TYPE, SENSOR_CHANNELS, FireEngine, FireFusion


# --- Modbus query/reply codec ---------------------------------------------------

def _reply(value: int, *, corrupt_crc: bool = False) -> bytes:
    """7-byte reply holding the signed int16 `value` for any register."""
    body = b"\x02\x03\x02" + (value & 0xFFFF).to_bytes(2, "big")
    crc = calc_crc16(body)
    if corrupt_crc:
        crc ^= 0xFFFF
    return body + bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def test_build_query_matches_known_flame_query() -> None:
    # Known-good frame for register 0x0007 from the sensor manual.
    assert build_query(0x0007) == bytes.fromhex("02 03 00 07 00 01 35 F8")


def test_registers_cover_all_seven_channels() -> None:
    assert REGISTERS == {
        "tvoc": 0x0001,
        "temperature": 0x0002,
        "humidity": 0x0003,
        "pm25": 0x0005,
        "flame": 0x0007,
        "light": 0x0008,
        "co2": 0x0009,
    }


def test_parse_register_reply_decodes_signed_values() -> None:
    assert parse_register_reply(_reply(1)) == 1
    assert parse_register_reply(_reply(0)) == 0
    assert parse_register_reply(_reply(-5)) == -5  # negative temperature


def test_parse_register_reply_rejects_bad_crc_and_short_reply() -> None:
    assert parse_register_reply(_reply(1, corrupt_crc=True)) is None
    assert parse_register_reply(b"\x02\x03") is None
    assert parse_register_reply(b"") is None


def test_default_sensor_port_is_platform_specific() -> None:
    port = default_sensor_port()
    assert isinstance(port, str) and port


# --- sensor monitor (fake serial) ----------------------------------------------

class _FakeSerial:
    """pyserial look-alike answering each query from a register->value script."""

    def __init__(self, values, corrupt=()):
        self._values = dict(values)
        self._corrupt = set(corrupt)
        self.queries: list[bytes] = []
        self.closed = False

    def reset_input_buffer(self) -> None:
        pass

    def reset_output_buffer(self) -> None:
        pass

    def write(self, data: bytes) -> int:
        self.queries.append(bytes(data))
        return len(data)

    def read(self, n: int) -> bytes:
        register = (self.queries[-1][2] << 8) | self.queries[-1][3]
        value = self._values.get(register)
        if value is None:
            return b""  # register never answers
        return _reply(value, corrupt_crc=register in self._corrupt)

    def close(self) -> None:
        self.closed = True


def _values(**channels) -> dict:
    return {REGISTERS[name]: value for name, value in channels.items()}


def test_sensor_monitor_polls_all_registers() -> None:
    fake = _FakeSerial(_values(
        tvoc=120, temperature=26, humidity=55, pm25=35, flame=1, light=300, co2=800,
    ))
    monitor = EnvSensorMonitor(
        port="COM-fake", poll_seconds=0.01, serial_factory=lambda: fake
    )
    assert monitor.start() is True
    try:
        deadline = time.monotonic() + 2.0
        while not monitor.flame_detected and time.monotonic() < deadline:
            time.sleep(0.01)
        assert monitor.flame_detected is True
        assert monitor.readings == {
            "tvoc": 120, "temperature": 26, "humidity": 55,
            "pm25": 35, "flame": 1, "light": 300, "co2": 800,
        }
        assert len(fake.queries) >= len(REGISTERS)
    finally:
        monitor.stop()
    assert fake.closed is True
    assert monitor.available is False


def test_sensor_monitor_open_failure_degrades_gracefully() -> None:
    def _broken():
        raise OSError("no such port")

    monitor = EnvSensorMonitor(port="COM-missing", serial_factory=_broken)
    assert monitor.start() is False   # degraded, no exception
    assert monitor.flame_detected is False
    assert all(value is None for value in monitor.readings.values())
    assert monitor.available is False
    monitor.stop()  # must not raise


def test_sensor_monitor_failed_register_becomes_none_without_aborting_round() -> None:
    # TVOC never answers, humidity answers with a corrupt CRC; the round must
    # still deliver the remaining registers.
    fake = _FakeSerial(
        _values(temperature=-3, humidity=60, pm25=35, flame=0, light=300, co2=800),
        corrupt={REGISTERS["humidity"]},
    )
    monitor = EnvSensorMonitor(port="COM-fake", serial_factory=lambda: fake)
    monitor._ser = fake  # drive poll_round directly, without the polling thread
    readings = monitor.poll_round()
    assert readings["tvoc"] is None
    assert readings["humidity"] is None
    assert readings["temperature"] == -3
    assert readings["co2"] == 800


# --- fusion ---------------------------------------------------------------------

class _FakePublisher:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def enqueue(self, **kwargs) -> None:
        self.events.append(kwargs)


def _fusion() -> tuple:
    pub = _FakePublisher()
    fusion = FireFusion(pub, store_id="store-main", device_id="front-cam-01", zone_id="front-hall")
    return fusion, pub


def _normal_readings() -> dict:
    return {
        "temperature": 25, "humidity": 50, "tvoc": 100,
        "co2": 700, "pm25": 30, "light": 300, "flame": 0,
    }


def _step(fusion: FireFusion, *, v: bool = False, vc: float = 0.85, now: float, readings=None):
    return fusion.update(
        vision_flag=v, vision_conf=vc,
        readings=readings if readings is not None else _normal_readings(),
        now=now,
    )


def test_fusion_single_channel_never_publishes() -> None:
    # Only vision ever fires.
    fusion, pub = _fusion()
    for t in (0.0, 1.0, 2.0):
        assert _step(fusion, v=True, now=t) is None
    assert pub.events == []
    # Only the flame sensor ever fires.
    fusion, pub = _fusion()
    for t in (0.0, 1.0, 2.0):
        readings = _normal_readings()
        readings["flame"] = 1
        assert _step(fusion, now=t, readings=readings) is None
    assert pub.events == []


def test_fusion_two_abnormal_channels_stay_below_vote_threshold() -> None:
    fusion, pub = _fusion()
    readings = _normal_readings()
    readings["temperature"] = 60   # > 45 °C
    readings["co2"] = 2000         # > 1500 ppm
    for t in (0.0, 1.0, 2.0):
        assert _step(fusion, now=t, readings=readings) is None
    assert pub.events == []


def test_fusion_stale_single_channel_does_not_fuse() -> None:
    # Vision fired 4s ago — outside the ±3s window when the flame sensor fires.
    fusion, pub = _fusion()
    assert _step(fusion, v=True, now=0.0) is None
    readings = _normal_readings()
    readings["flame"] = 1
    assert _step(fusion, now=4.0, readings=readings) is None
    assert pub.events == []


def test_fusion_vision_flame_dual_channel_publishes_warning() -> None:
    fusion, pub = _fusion()
    readings = _normal_readings()
    readings["flame"] = 1
    payload = _step(fusion, v=True, now=0.0, readings=readings)
    assert payload is not None
    assert payload["event_subtype"] == "flame_dual_confirm"
    assert payload["triggered_rule"] == "vision_flame"
    assert payload["vote_count"] == 2
    assert payload["abnormal_channels"] == ["vision", "flame"]
    assert payload["zone_id"] == "front-hall"
    assert payload["vision_conf"] == 0.85
    assert payload["confidence"] == 0.85
    assert payload["sensor_state"] == 1
    assert payload["duration_ms"] == 0
    assert payload["readings"]["flame"] == 1
    assert payload["readings"]["temperature"] == 25
    assert payload["readings"]["vision_conf"] == 0.85
    assert len(pub.events) == 1
    event = pub.events[0]
    assert event["event_type"] == EVENT_TYPE == "vision.front.fire"
    assert event["severity"] == "warning"


def test_fusion_three_abnormal_channels_trigger_vote3() -> None:
    fusion, pub = _fusion()
    readings = _normal_readings()
    readings["temperature"] = 60   # > 45 °C
    readings["humidity"] = 10      # < 20 %RH
    readings["pm25"] = 300         # > 150 μg/m³
    payload = _step(fusion, now=0.0, readings=readings)
    assert payload is not None
    assert payload["triggered_rule"] == "vote3"
    assert payload["vote_count"] == 3
    assert payload["abnormal_channels"] == ["temperature", "humidity", "pm25"]
    assert pub.events[0]["severity"] == "warning"


def test_fusion_vote3_wins_over_vision_flame_when_both_hold() -> None:
    fusion, pub = _fusion()
    readings = _normal_readings()
    readings["flame"] = 1
    readings["tvoc"] = 900         # vision + flame + tvoc = 3 votes
    payload = _step(fusion, v=True, now=0.0, readings=readings)
    assert payload is not None
    assert payload["triggered_rule"] == "vote3"
    assert payload["vote_count"] == 3


def test_fusion_unread_channels_count_as_normal() -> None:
    # All sensor readings None (port degraded): vision alone never publishes.
    fusion, pub = _fusion()
    none_readings = {name: None for name in SENSOR_CHANNELS}
    for t in (0.0, 1.0, 2.0):
        assert _step(fusion, v=True, now=t, readings=none_readings) is None
    assert pub.events == []


def test_fusion_offset_within_window_still_fuses() -> None:
    fusion, pub = _fusion()
    assert _step(fusion, v=True, now=0.0) is None
    readings = _normal_readings()
    readings["flame"] = 1
    payload = _step(fusion, now=2.0, readings=readings)   # ±3s window
    assert payload is not None
    assert payload["triggered_rule"] == "vision_flame"
    assert len(pub.events) == 1


def test_fusion_cooldown_dedupes_repeat_warnings() -> None:
    fusion, pub = _fusion()
    readings = _normal_readings()
    readings["flame"] = 1
    assert _step(fusion, v=True, now=0.0, readings=readings) is not None
    assert _step(fusion, v=True, now=5.0, readings=readings) is None   # same episode, <10s
    assert len(pub.events) == 1


def test_fusion_sustained_episode_escalates_to_critical() -> None:
    fusion, pub = _fusion()
    readings = _normal_readings()
    readings["flame"] = 1
    assert _step(fusion, v=True, now=0.0, readings=readings)["duration_ms"] == 0
    payload = _step(fusion, v=True, now=11.0, readings=readings)       # >10s sustained
    assert payload is not None
    assert payload["duration_ms"] == 11000
    assert pub.events[-1]["severity"] == "critical"
    assert len(pub.events) == 2
    assert _step(fusion, v=True, now=12.0, readings=readings) is None  # escalate once


def test_fusion_retrigger_during_cooldown_is_critical() -> None:
    fusion, pub = _fusion()
    readings = _normal_readings()
    readings["flame"] = 1
    _step(fusion, v=True, now=0.0, readings=readings)
    _step(fusion, now=4.0)                              # episode ends (stale)
    payload = _step(fusion, v=True, now=10.0, readings=readings)   # re-trigger inside 30s cooldown
    assert payload is not None
    assert pub.events[-1]["severity"] == "critical"
    assert len(pub.events) == 2


def test_fusion_after_cooldown_publishes_warning_again() -> None:
    fusion, pub = _fusion()
    readings = _normal_readings()
    readings["flame"] = 1
    _step(fusion, v=True, now=0.0, readings=readings)
    _step(fusion, now=4.0)
    payload = _step(fusion, v=True, now=35.0, readings=readings)   # cooldown expired
    assert payload is not None
    assert pub.events[-1]["severity"] == "warning"
    assert len(pub.events) == 2


def test_fire_envelope_passes_local_schema() -> None:
    fusion, pub = _fusion()
    readings = _normal_readings()
    readings["flame"] = 1
    _step(fusion, v=True, now=0.0, readings=readings)
    envelope = build_envelope(**pub.events[0])
    validate_envelope(envelope, ENVELOPE_SCHEMA_PATH)


def test_alert_state_exposes_vote_details_for_the_banner() -> None:
    fusion, pub = _fusion()
    readings = _normal_readings()
    readings["flame"] = 1
    _step(fusion, v=True, now=0.0, readings=readings)
    alert = fusion.alert_state(now=1.0)
    assert alert["vote_count"] == 2
    assert alert["abnormal_channels"] == ["vision", "flame"]
    assert alert["triggered_rule"] == "vision_flame"
    assert fusion.alert_state(now=10.0) is None   # banner hides after a few seconds


# --- engine throttling (fake detector + fake sensor) ----------------------------

class _FakeVision:
    def __init__(self) -> None:
        self.calls = 0

    def analyze(self, frame):
        self.calls += 1
        return 0.9, True


class _FakeSensor:
    def __init__(self, readings) -> None:
        self.readings = readings

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        pass


def test_engine_throttles_vision_and_fuses_dual_channels() -> None:
    config = FrontVisionConfig()
    config.fire_infer_every_n_frames = 3
    pub = _FakePublisher()
    vision = _FakeVision()
    readings = _normal_readings()
    readings["flame"] = 1
    engine = FireEngine(config, pub, vision_detector=vision, sensor_monitor=_FakeSensor(readings))

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    payload = None
    for i in range(5):
        payload = engine.update(frame, now=float(i) * 0.1) or payload

    # Frames 1 and 4 ran inference; frames 2, 3, 5 reused the cached result.
    assert vision.calls == 2
    # Cached vision flag still fuses with the live sensor state.
    assert payload is not None
    assert payload["triggered_rule"] == "vision_flame"
    assert pub.events and pub.events[0]["event_type"] == "vision.front.fire"


def test_engine_vote3_publishes_without_vision() -> None:
    config = FrontVisionConfig()
    pub = _FakePublisher()
    readings = _normal_readings()
    readings["temperature"] = 60
    readings["humidity"] = 10
    readings["tvoc"] = 900
    engine = FireEngine(config, pub, vision_detector=None, sensor_monitor=_FakeSensor(readings))

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    payload = engine.update(frame, now=0.0)
    assert payload is not None
    assert payload["triggered_rule"] == "vote3"
    assert payload["abnormal_channels"] == ["temperature", "humidity", "tvoc"]


def test_engine_without_sensor_never_publishes() -> None:
    config = FrontVisionConfig()
    pub = _FakePublisher()
    engine = FireEngine(config, pub, vision_detector=_FakeVision(), sensor_monitor=None)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    for i in range(3):
        assert engine.update(frame, now=float(i) * 0.1) is None
    assert pub.events == []
