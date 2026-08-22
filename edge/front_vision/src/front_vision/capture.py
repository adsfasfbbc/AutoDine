"""Frame capture: camera (DirectShow) or looping video file.

A background thread continuously grabs frames and shares only the latest one.
Frames are kept in memory exclusively; nothing is ever written to disk
(privacy requirement: no face or frame images are persisted).
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("front_vision.capture")


class FrameSource:
    """Thread-safe provider of the most recent frame."""

    def __init__(
        self,
        source: str = "camera",
        camera_index: int = 0,
        width: int = 640,
        height: int = 480,
        loop_video: bool = True,
    ) -> None:
        self._source = source
        self._camera_index = camera_index
        self._width = width
        self._height = height
        self._loop_video = loop_video
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.frames_captured = 0

    # -- lifecycle ---------------------------------------------------------
    def open(self) -> None:
        if self._source == "camera":
            cap = cv2.VideoCapture(self._camera_index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                raise RuntimeError(f"cannot open camera index {self._camera_index} (DirectShow)")
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        else:
            cap = cv2.VideoCapture(self._source)
            if not cap.isOpened():
                raise RuntimeError(f"cannot open video source {self._source}")
        self._cap = cap
        logger.info("capture source opened: %s", self._source)

    def start(self) -> None:
        if self._cap is None:
            self.open()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="front-vision-capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self) -> "FrameSource":
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()

    # -- internals ---------------------------------------------------------
    def _grab(self) -> bool:
        assert self._cap is not None
        ok, frame = self._cap.read()
        if not ok:
            if self._source != "camera" and self._loop_video:
                # Video file ended: rewind and keep looping for smoke tests.
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                return False
            return False
        if frame.shape[1] != self._width or frame.shape[0] != self._height:
            frame = cv2.resize(frame, (self._width, self._height))
        with self._lock:
            self._frame = frame
        self.frames_captured += 1
        return True

    def _run(self) -> None:
        failures = 0
        while not self._stop.is_set():
            try:
                if not self._grab():
                    failures += 1
                    time.sleep(0.05)
                    if failures > 200:
                        logger.error("capture keeps failing; giving up reads")
                        return
                else:
                    failures = 0
                    # Small yield so a fast video-file loop doesn't spin at 100%.
                    if self._source != "camera":
                        time.sleep(0.01)
            except Exception:
                logger.exception("capture loop error")
                time.sleep(0.2)

    # -- access ------------------------------------------------------------
    def latest(self) -> Optional[np.ndarray]:
        """Return the newest frame (shared reference; treat as read-only)."""
        with self._lock:
            return self._frame

    def latest_shape(self) -> Optional[Tuple[int, int]]:
        frame = self.latest()
        if frame is None:
            return None
        return (frame.shape[1], frame.shape[0])
