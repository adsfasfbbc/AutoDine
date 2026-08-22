"""Dual-modality safety fusion: vision violent-interaction AND acoustic
high-arousal must co-occur within a ±3s window before a vision.front.safety
event is published. Single-modality cues only get a debug log.

Severity: warning by default; escalates to critical when the episode lasts
longer than the critical threshold or when it re-triggers inside the
cooldown window. A 30s cooldown deduplicates repeat publications.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger("front_vision.safety_fusion")

EVENT_TYPE = "vision.front.safety"
EVENT_SUBTYPE = "violent_interaction"
# How long the GUI/web banner stays up after a trigger (display-only state).
ALERT_BANNER_SECONDS = 5.0


class SafetyFusion:
    """Time-window AND fusion with cooldown dedup and severity escalation."""

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
    ) -> None:
        self._publisher = publisher
        self._store_id = store_id
        self._device_id = device_id
        self._zone_id = zone_id
        self._window = window_seconds
        self._cooldown = cooldown_seconds
        self._critical_after = critical_after_seconds

        self._vision_at: Optional[float] = None
        self._audio_at: Optional[float] = None
        self._episode_start: Optional[float] = None
        self._cooldown_until = 0.0
        self._escalated = False
        self.last_alert: Optional[dict] = None

    def _co_occurring(self, now: float) -> bool:
        return (
            self._vision_at is not None
            and self._audio_at is not None
            and now - self._vision_at <= self._window
            and now - self._audio_at <= self._window
            and abs(self._vision_at - self._audio_at) <= self._window
        )

    def update(
        self,
        *,
        vision_flag: bool,
        vision_score: float,
        audio_flag: bool,
        audio_score: float,
        now: Optional[float] = None,
    ) -> Optional[dict]:
        """Feed one fusion step; returns the published payload (or None)."""
        now = time.monotonic() if now is None else now
        if vision_flag:
            self._vision_at = now
        if audio_flag:
            self._audio_at = now

        if not self._co_occurring(now):
            if vision_flag != audio_flag:
                logger.debug(
                    "single-modality safety cue only (vision=%s/%.2f, audio=%s/%.2f); not publishing",
                    vision_flag, vision_score, audio_flag, audio_score,
                )
            if self._episode_start is not None and now - max(
                self._vision_at or 0.0, self._audio_at or 0.0
            ) > self._window:
                # Episode over: both cues went stale.
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
            return self._publish(severity, vision_score, audio_score, duration_ms=0, now=now)

        duration_ms = int((now - self._episode_start) * 1000)
        if not self._escalated and (now - self._episode_start) > self._critical_after:
            self._escalated = True
            self._cooldown_until = now + self._cooldown
            return self._publish("critical", vision_score, audio_score, duration_ms=duration_ms, now=now)
        return None

    def _publish(
        self,
        severity: str,
        vision_score: float,
        audio_score: float,
        *,
        duration_ms: int,
        now: float,
    ) -> dict:
        payload = {
            "event_subtype": EVENT_SUBTYPE,
            "confidence": round((vision_score + audio_score) / 2.0, 4),
            "vision_score": round(float(vision_score), 4),
            "audio_score": round(float(audio_score), 4),
            "duration_ms": duration_ms,
            "zone_id": self._zone_id,
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
            "vision_score": payload["vision_score"],
            "audio_score": payload["audio_score"],
        }
        logger.warning(
            "safety event %s severity=%s confidence=%.2f duration_ms=%d",
            EVENT_TYPE, severity, payload["confidence"], duration_ms,
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


class SafetyEngine:
    """Coordinates the pose analyzer, audio monitor and fusion for the
    inference pipeline. In simulate mode it injects a deterministic
    dual-modality pattern instead (demo without real people)."""

    def __init__(
        self,
        config,
        publisher,
        vision_analyzer=None,
        audio_monitor=None,
        fusion: Optional[SafetyFusion] = None,
        simulate: bool = False,
    ) -> None:
        self._config = config
        self._vision = vision_analyzer
        self._audio = audio_monitor
        self._simulate = simulate
        self._started_at: Optional[float] = None
        self.fusion = fusion or SafetyFusion(
            publisher,
            store_id=config.store_id,
            device_id=config.device_id,
            zone_id=config.safety_zone_id,
            window_seconds=config.safety_fusion_window_seconds,
            cooldown_seconds=config.safety_cooldown_seconds,
            critical_after_seconds=config.safety_critical_after_seconds,
        )

    def start(self) -> None:
        self._started_at = time.monotonic()
        if self._audio is not None:
            self._audio.start()

    def stop(self) -> None:
        if self._audio is not None:
            self._audio.stop()

    def update(self, frame, now: Optional[float] = None) -> Optional[dict]:
        """One fusion step on the newest frame; returns published payload."""
        now = time.monotonic() if now is None else now
        if self._simulate:
            vision_score, vision_flag = self._simulated(now)
            audio_score, audio_flag = self._simulated(now, offset=0.5)
        else:
            vision_score, vision_flag = 0.0, False
            if self._vision is not None:
                vision_score, vision_flag = self._vision.analyze(frame, now=now)
            audio_score, audio_flag = 0.0, False
            if self._audio is not None:
                audio_score, audio_flag = self._audio.audio_score, self._audio.audio_flag
        return self.fusion.update(
            vision_flag=vision_flag, vision_score=vision_score,
            audio_flag=audio_flag, audio_score=audio_score, now=now,
        )

    def _simulated(self, now: float, offset: float = 0.0) -> tuple:
        """Both modalities 'active' for seconds [5, 20) of every 60s cycle."""
        phase = ((now - (self._started_at or now)) + offset) % 60.0
        active = 5.0 <= phase < 20.0
        return (0.85 if active else 0.1), active

    def alert_state(self, now: Optional[float] = None) -> Optional[dict]:
        return self.fusion.alert_state(now)
