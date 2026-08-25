"""Fire multi-channel fusion: eight channels vote on a fire before a
vision.front.fire event is published.

Channels: flame vision (YOLO), flame sensor, temperature, humidity, TVOC,
CO2, PM2.5 and light. Each channel yields an abnormal boolean plus its raw
reading. Two trigger rules:

- Rule A ("vote3"): at least `vote_threshold` channels (default 3) are
  abnormal at the same time.
- Rule B ("vision_flame"): flame vision AND the flame sensor co-occur within
  a ±window (the original dual confirmation).

Severity: warning by default; escalates to critical when the episode lasts
longer than the critical threshold or when it re-triggers inside the
cooldown window. A 30s cooldown deduplicates repeat publications.
"""
from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("front_vision.fire_fusion")

EVENT_TYPE = "vision.front.fire"
EVENT_SUBTYPE = "flame_dual_confirm"
# How long the GUI/web banner stays up after a trigger (display-only state).
ALERT_BANNER_SECONDS = 5.0

# All voting channels, in a stable order for payloads and logs.
CHANNELS = ("vision", "flame", "temperature", "humidity", "tvoc", "co2", "pm25", "light")

# Sensor channels whose raw value snapshots travel in the payload.
SENSOR_CHANNELS = ("temperature", "humidity", "tvoc", "co2", "pm25", "light", "flame")


class FireFusion:
    """8-channel voting fusion with cooldown dedup and severity escalation."""

    def __init__(
        self,
        publisher,
        *,
        store_id: str,
        device_id: Optional[str] = None,
        zone_id: str = "front-hall",
        window_seconds: float = 3.0,
        cooldown_seconds: float = 30.0,
        critical_after_seconds: float = 10.0,
        vote_threshold: int = 3,
        temp_threshold: float = 45.0,
        humidity_threshold: float = 20.0,
        tvoc_threshold: float = 600.0,
        co2_threshold: float = 1500.0,
        pm25_threshold: float = 150.0,
        light_threshold: float = 1000.0,
    ) -> None:
        self._publisher = publisher
        self._store_id = store_id
        self._device_id = device_id
        self._zone_id = zone_id
        self._window = window_seconds
        self._cooldown = cooldown_seconds
        self._critical_after = critical_after_seconds
        self._vote_threshold = vote_threshold
        self._temp_threshold = temp_threshold
        self._humidity_threshold = humidity_threshold
        self._tvoc_threshold = tvoc_threshold
        self._co2_threshold = co2_threshold
        self._pm25_threshold = pm25_threshold
        self._light_threshold = light_threshold

        self._vision_at: Optional[float] = None
        self._flame_at: Optional[float] = None
        self._episode_start: Optional[float] = None
        self._cooldown_until = 0.0
        self._escalated = False
        self.last_alert: Optional[dict] = None

    def _abnormal_channels(
        self, *, vision_flag: bool, readings: Dict[str, Optional[float]]
    ) -> List[str]:
        """Per-channel abnormal booleans -> ordered list of abnormal channels."""
        def _get(name: str) -> Optional[float]:
            return readings.get(name)

        abnormal = {
            "vision": vision_flag,
            "flame": _get("flame") == 1,
            "temperature": _get("temperature") is not None
                and _get("temperature") > self._temp_threshold,
            "humidity": _get("humidity") is not None
                and _get("humidity") < self._humidity_threshold,
            "tvoc": _get("tvoc") is not None and _get("tvoc") > self._tvoc_threshold,
            "co2": _get("co2") is not None and _get("co2") > self._co2_threshold,
            "pm25": _get("pm25") is not None and _get("pm25") > self._pm25_threshold,
            "light": _get("light") is not None and _get("light") > self._light_threshold,
        }
        return [name for name in CHANNELS if abnormal[name]]

    def _vision_flame_co_occurring(self, now: float) -> bool:
        return (
            self._vision_at is not None
            and self._flame_at is not None
            and now - self._vision_at <= self._window
            and now - self._flame_at <= self._window
            and abs(self._vision_at - self._flame_at) <= self._window
        )

    def update(
        self,
        *,
        vision_flag: bool,
        vision_conf: float,
        readings: Optional[Dict[str, Optional[float]]] = None,
        now: Optional[float] = None,
    ) -> Optional[dict]:
        """Feed one fusion step; returns the published payload (or None).

        `readings` holds the latest raw values for the seven sensor channels
        (None = unread/failed). Abnormal channels never read count as normal.
        """
        now = time.monotonic() if now is None else now
        readings = readings or {}
        abnormal = self._abnormal_channels(vision_flag=vision_flag, readings=readings)
        vote_count = len(abnormal)

        if vision_flag:
            self._vision_at = now
        if readings.get("flame") == 1:
            self._flame_at = now

        if vote_count >= self._vote_threshold:
            triggered_rule = "vote3"
        elif self._vision_flame_co_occurring(now):
            triggered_rule = "vision_flame"
        else:
            triggered_rule = None

        if triggered_rule is None:
            if abnormal:
                logger.debug(
                    "fire channels abnormal but below trigger (votes=%d/%d %s); not publishing",
                    vote_count, self._vote_threshold, abnormal,
                )
            if self._episode_start is not None and now - max(
                self._vision_at or 0.0, self._flame_at or 0.0
            ) > self._window:
                # Episode over: all cues went stale.
                self._episode_start = None
            return None

        if self._episode_start is None:
            # New episode. A re-trigger inside the cooldown escalates to
            # critical instead of being deduplicated away.
            self._episode_start = now
            in_cooldown = now < self._cooldown_until
            severity = "critical" if in_cooldown else "warning"
            self._escalated = in_cooldown
            self._cooldown_until = now + self._cooldown
            return self._publish(
                severity, vision_conf, readings, abnormal, triggered_rule,
                duration_ms=0, now=now,
            )

        duration_ms = int((now - self._episode_start) * 1000)
        if not self._escalated and (now - self._episode_start) > self._critical_after:
            self._escalated = True
            self._cooldown_until = now + self._cooldown
            return self._publish(
                "critical", vision_conf, readings, abnormal, triggered_rule,
                duration_ms=duration_ms, now=now,
            )
        return None

    def _publish(
        self,
        severity: str,
        vision_conf: float,
        readings: Dict[str, Optional[float]],
        abnormal_channels: List[str],
        triggered_rule: str,
        *,
        duration_ms: int,
        now: float,
    ) -> dict:
        snapshot = {
            name: readings.get(name) for name in SENSOR_CHANNELS
        }
        snapshot["vision_conf"] = round(float(vision_conf), 4)
        flame_state = readings.get("flame")
        payload = {
            "event_subtype": EVENT_SUBTYPE,
            "confidence": round(float(vision_conf), 4),
            "vision_conf": round(float(vision_conf), 4),
            "sensor_state": int(flame_state) if flame_state is not None else 0,
            "duration_ms": duration_ms,
            "zone_id": self._zone_id,
            "vote_count": len(abnormal_channels),
            "abnormal_channels": list(abnormal_channels),
            "triggered_rule": triggered_rule,
            "readings": snapshot,
        }
        self._publisher.enqueue(
            event_type=EVENT_TYPE,
            payload=payload,
            store_id=self._store_id,
            device_id=self._device_id,
            severity=severity,
        )
        self.last_alert = {
            "at": now,
            "severity": severity,
            "vision_conf": payload["vision_conf"],
            "sensor_state": payload["sensor_state"],
            "vote_count": payload["vote_count"],
            "abnormal_channels": payload["abnormal_channels"],
            "triggered_rule": triggered_rule,
        }
        logger.warning(
            "fire event %s severity=%s rule=%s votes=%d channels=%s confidence=%.2f duration_ms=%d",
            EVENT_TYPE, severity, triggered_rule, payload["vote_count"],
            payload["abnormal_channels"], payload["confidence"], duration_ms,
        )
        return payload

    def alert_state(self, now: Optional[float] = None) -> Optional[dict]:
        """Newest alert for the GUI/web banner, hidden after a few seconds."""
        if self.last_alert is None:
            return None
        now = time.monotonic() if now is None else now
        if now - self.last_alert["at"] > ALERT_BANNER_SECONDS:
            return None
        return dict(self.last_alert)


class FireEngine:
    """Coordinates the flame detector, environmental sensor monitor and fusion
    for the inference pipeline. Flame inference is throttled (every Nth
    pipeline frame) because running the model per frame is expensive. In
    simulate mode it injects a deterministic dual-channel pattern instead
    (demo without a real fire)."""

    def __init__(
        self,
        config,
        publisher,
        vision_detector=None,
        sensor_monitor=None,
        fusion: Optional[FireFusion] = None,
        simulate: bool = False,
    ) -> None:
        self._config = config
        self._vision = vision_detector
        self._sensor = sensor_monitor
        self._simulate = simulate
        self._started_at: Optional[float] = None
        self._frame_idx = 0
        self._last_vision: Tuple[float, bool] = (0.0, False)
        self.fusion = fusion or FireFusion(
            publisher,
            store_id=config.store_id,
            device_id=config.device_id,
            zone_id=config.fire_zone_id,
            window_seconds=config.fire_fusion_window_seconds,
            cooldown_seconds=config.fire_cooldown_seconds,
            critical_after_seconds=config.fire_critical_after_seconds,
            vote_threshold=config.fire_vote_threshold,
            temp_threshold=config.fire_temp_threshold,
            humidity_threshold=config.fire_humidity_threshold,
            tvoc_threshold=config.fire_tvoc_threshold,
            co2_threshold=config.fire_co2_threshold,
            pm25_threshold=config.fire_pm25_threshold,
            light_threshold=config.fire_light_threshold,
        )

    def start(self) -> None:
        self._started_at = time.monotonic()
        if self._sensor is not None:
            self._sensor.start()

    def stop(self) -> None:
        if self._sensor is not None:
            self._sensor.stop()

    def update(self, frame, now: Optional[float] = None) -> Optional[dict]:
        """One fusion step on the newest frame; returns published payload."""
        now = time.monotonic() if now is None else now
        if self._simulate:
            vision_conf, vision_flag = self._simulated(now)
            readings = {name: None for name in SENSOR_CHANNELS}
            readings["flame"] = 1 if vision_flag else 0
        else:
            self._frame_idx += 1
            vision_conf, vision_flag = self._last_vision
            every = max(1, self._config.fire_infer_every_n_frames)
            if self._vision is not None and (self._frame_idx - 1) % every == 0:
                vision_conf, vision_flag = self._vision.analyze(frame)
                self._last_vision = (vision_conf, vision_flag)
            readings = {name: None for name in SENSOR_CHANNELS}
            if self._sensor is not None:
                readings.update(self._sensor.readings)
        return self.fusion.update(
            vision_flag=vision_flag, vision_conf=vision_conf,
            readings=readings, now=now,
        )

    def _simulated(self, now: float) -> tuple:
        """Both flame channels 'active' for seconds [5, 20) of every 60s cycle."""
        phase = ((now - (self._started_at or now)) + 0.5) % 60.0
        active = 5.0 <= phase < 20.0
        return (0.9 if active else 0.05), active

    def alert_state(self, now: Optional[float] = None) -> Optional[dict]:
        return self.fusion.alert_state(now)
