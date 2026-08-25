"""Inference + publishing pipeline for the front_vision edge service.

Runs in a background thread: pulls the newest frame from the capture loop,
counts people (smoothed, published as queue.updated), runs the safety
fusion engine (vision pose + acoustic arousal -> vision.front.safety) and
the fire multi-channel fusion engine (flame vision + Modbus environmental
sensor voting -> vision.front.fire).
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from .adp import AdpPublisher
from .capture import FrameSource
from .config import FrontVisionConfig
from .fire_fusion import FireEngine
from .people import CountSmoother, PersonDetector, count_in_roi
from .safety_fusion import SafetyEngine

logger = logging.getLogger("front_vision.pipeline")


class FrontVisionPipeline:
    def __init__(
        self,
        config: FrontVisionConfig,
        publisher: AdpPublisher,
        capture: FrameSource,
        detector: PersonDetector,
        safety: Optional[SafetyEngine] = None,
        fire: Optional[FireEngine] = None,
    ) -> None:
        self._config = config
        self._publisher = publisher
        self._capture = capture
        self._detector = detector
        self._safety = safety
        self._fire = fire
        self._smoother = CountSmoother(config.smooth_window_seconds)

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Mutable metrics exposed via /metrics.
        self.current_count = 0
        self.last_frame_at: Optional[float] = None
        self.frames_inferred = 0

        self._last_published_count: Optional[int] = None
        self._last_queue_publish = 0.0

        # MJPEG debug preview: only the newest annotated JPEG, in memory.
        self._preview_jpeg: Optional[bytes] = None
        self._preview_lock = threading.Lock()
        self.inference_fps = 0.0
        self._last_infer_mono: Optional[float] = None

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        self._stop.clear()
        self._publisher.start_worker()
        if self._safety is not None:
            self._safety.start()
        if self._fire is not None:
            self._fire.start()
        self._thread = threading.Thread(target=self._run, name="front-vision-pipeline", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._safety is not None:
            self._safety.stop()
        if self._fire is not None:
            self._fire.stop()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    @property
    def backend_name(self) -> str:
        return self._detector.backend_name

    def safety_alert(self) -> Optional[dict]:
        """Newest safety alert for the GUI/web banner (None when inactive)."""
        if self._safety is None:
            return None
        return self._safety.alert_state()

    def fire_alert(self) -> Optional[dict]:
        """Newest fire alert for the GUI/web banner (None when inactive)."""
        if self._fire is None:
            return None
        return self._fire.alert_state()

    # -- publishing --------------------------------------------------------
    def publish_queue_update(self, count: int) -> None:
        self._publisher.enqueue(
            event_type="queue.updated",
            payload={"zone_id": self._config.queue_zone_id, "waiting_count": int(count)},
            store_id=self._config.store_id,
            device_id=self._config.device_id,
            severity="info",
        )
        self._last_published_count = count
        self._last_queue_publish = time.monotonic()

    # -- main loop ---------------------------------------------------------
    def _run(self) -> None:
        frame_idx = 0
        while not self._stop.is_set():
            frame = self._capture.latest()
            if frame is None:
                time.sleep(0.05)
                continue
            frame_idx += 1
            if frame_idx % max(1, self._config.infer_every_n_frames) != 0:
                time.sleep(0.01)
                continue
            try:
                self._process_frame(frame)
            except Exception:
                logger.exception("inference iteration failed")
                time.sleep(0.2)

    def _process_frame(self, frame) -> None:
        cfg = self._config
        now = time.monotonic()
        with self._lock:
            self.last_frame_at = time.time()
            self.frames_inferred += 1
        if self._last_infer_mono is not None:
            dt = now - self._last_infer_mono
            if dt > 0:
                self.inference_fps = 0.9 * self.inference_fps + 0.1 * (1.0 / dt)
        self._last_infer_mono = now

        # --- people counting ------------------------------------------------
        detections = self._detector.detect_with_scores(frame)
        boxes = [b for b, _ in detections]
        frame_size = (frame.shape[1], frame.shape[0])
        raw_count = count_in_roi(boxes, cfg.queue_roi, frame_size)
        smoothed = self._smoother.add(raw_count)
        with self._lock:
            self.current_count = smoothed

        count_changed = smoothed != self._last_published_count
        heartbeat_due = (now - self._last_queue_publish) >= cfg.queue_heartbeat_seconds
        if count_changed or heartbeat_due:
            self.publish_queue_update(smoothed)

        # --- safety fusion (vision pose AND acoustic arousal) --------------
        if self._safety is not None:
            self._safety.update(frame, now)

        # --- fire fusion (8-channel voting: flame vision + env sensor) -----
        if self._fire is not None:
            self._fire.update(frame, now)

        # --- debug preview frame (memory-only, zero cost when disabled) -----
        if cfg.preview_enabled:
            self._annotate_and_store(frame, detections, smoothed)

    def _annotate_and_store(self, frame, detections, smoothed_count: int) -> None:
        """Draw boxes/labels on a copy of the frame and keep only the newest JPEG."""
        import cv2

        annotated = frame.copy()
        for (x1, y1, x2, y2), score in detections:
            cv2.rectangle(annotated, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            cv2.putText(
                annotated, f"person {score:.2f}", (int(x1), max(15, int(y1) - 6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1,
            )
        cv2.putText(
            annotated, f"count={smoothed_count} fps={self.inference_fps:.1f}", (8, 24),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2,
        )
        alert = self.safety_alert()
        if alert is not None:
            cv2.putText(
                annotated, f"SAFETY {alert['severity']}", (8, 52),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2,
            )
        fire = self.fire_alert()
        if fire is not None:
            cv2.putText(
                annotated,
                f"FIRE {fire['severity']} votes={fire.get('vote_count', 0)}/8",
                (8, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2,
            )
        ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ok:
            with self._preview_lock:
                self._preview_jpeg = buf.tobytes()

    def preview_jpeg(self) -> Optional[bytes]:
        """Newest annotated frame as JPEG bytes (None until first inference)."""
        with self._preview_lock:
            return self._preview_jpeg
