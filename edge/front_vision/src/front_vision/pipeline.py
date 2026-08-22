"""Inference + publishing pipeline for the front_vision edge service.

Runs in a background thread: pulls the newest frame from the capture loop,
counts people (smoothed, published as queue.updated), recognizes face
emotions (aggregated, published as customer.experience_summary).
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from .adp import AdpPublisher
from .aggregator import EmotionAggregator
from .capture import FrameSource
from .config import FrontVisionConfig
from .people import CountSmoother, PersonDetector, count_in_roi

logger = logging.getLogger("front_vision.pipeline")


class FrontVisionPipeline:
    def __init__(
        self,
        config: FrontVisionConfig,
        publisher: AdpPublisher,
        capture: FrameSource,
        detector: PersonDetector,
        emotion_analyzer=None,
    ) -> None:
        self._config = config
        self._publisher = publisher
        self._capture = capture
        self._detector = detector
        self._emotion_analyzer = emotion_analyzer
        self._smoother = CountSmoother(config.smooth_window_seconds)
        self._aggregator = EmotionAggregator(config.emotion_window_seconds)

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Mutable metrics exposed via /metrics.
        self.current_count = 0
        self.last_frame_at: Optional[float] = None
        self.last_emotion_summary = self._aggregator.summarize()
        self.frames_inferred = 0

        self._last_published_count: Optional[int] = None
        self._last_queue_publish = 0.0
        self._last_emotion_publish = time.monotonic()

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        self._stop.clear()
        self._publisher.start_worker()
        self._thread = threading.Thread(target=self._run, name="front-vision-pipeline", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    @property
    def backend_name(self) -> str:
        return self._detector.backend_name

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

    def publish_emotion_summary(self) -> None:
        summary = self._aggregator.summarize()
        with self._lock:
            self.last_emotion_summary = summary
        if summary["sample_count"] == 0:
            logger.debug("emotion window empty; skipping customer.experience_summary")
            return
        self._publisher.enqueue(
            event_type="customer.experience_summary",
            payload=summary,
            store_id=self._config.store_id,
            device_id=self._config.device_id,
            severity="info",
        )

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

        # --- people counting ------------------------------------------------
        boxes = self._detector.detect(frame)
        frame_size = (frame.shape[1], frame.shape[0])
        raw_count = count_in_roi(boxes, cfg.queue_roi, frame_size)
        smoothed = self._smoother.add(raw_count)
        with self._lock:
            self.current_count = smoothed

        count_changed = smoothed != self._last_published_count
        heartbeat_due = (now - self._last_queue_publish) >= cfg.queue_heartbeat_seconds
        if count_changed or heartbeat_due:
            self.publish_queue_update(smoothed)

        # --- emotion recognition -------------------------------------------
        if self._emotion_analyzer is not None:
            for sentiment in self._emotion_analyzer.analyze(frame):
                self._aggregator.add(sentiment)

        if (now - self._last_emotion_publish) >= cfg.emotion_publish_seconds:
            self._last_emotion_publish = now
            self.publish_emotion_summary()
