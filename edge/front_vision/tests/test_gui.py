"""Offscreen tests for the PySide6 debug window (no display required)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import threading

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from front_vision.gui import WINDOW_TITLE, FrontVisionWindow, NullPublisher


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class _StubPipeline:
    """Minimal stand-in for FrontVisionPipeline (no capture/inference)."""

    def __init__(self, jpeg: bytes | None = None, alert: dict | None = None):
        self._lock = threading.Lock()
        self.current_count = 3
        self.inference_fps = 12.34
        self._jpeg = jpeg
        self._alert = alert

    @property
    def backend_name(self) -> str:
        return "stub-backend"

    def preview_jpeg(self):
        return self._jpeg

    def safety_alert(self):
        return self._alert


def _make_jpeg() -> bytes:
    import cv2
    import numpy as np

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(frame, "count=3", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    ok, buf = cv2.imencode(".jpg", frame)
    assert ok
    return buf.tobytes()


def test_window_title_and_metrics(qapp):
    window = FrontVisionWindow(_StubPipeline(), publisher=NullPublisher())
    assert window.windowTitle() == WINDOW_TITLE

    window.refresh()
    assert window._count_label.text() == "3"
    assert window._backend_label.text() == "stub-backend"
    assert window._fps_label.text() == "12.3"
    assert "disabled" in window._publish_label.text()


def test_window_displays_annotated_frame(qapp):
    window = FrontVisionWindow(_StubPipeline(jpeg=_make_jpeg()))
    assert window._video_label.pixmap().isNull()
    window.refresh()
    assert not window._video_label.pixmap().isNull()


def test_window_without_frame_keeps_placeholder(qapp):
    window = FrontVisionWindow(_StubPipeline(jpeg=None))
    window.refresh()
    assert window._video_label.pixmap().isNull()
    assert window._video_label.text() == "waiting for frames..."


def test_safety_banner_shows_and_hides(qapp):
    alert = {"severity": "critical", "vision_score": 0.8, "audio_score": 0.7, "at": 0.0}
    window = FrontVisionWindow(_StubPipeline(alert=alert))
    window.refresh()
    assert not window._banner.isHidden()
    assert "CRITICAL" in window._banner.text()

    window._pipeline._alert = None
    window.refresh()
    assert window._banner.isHidden()


def test_null_publisher_is_a_noop():
    publisher = NullPublisher()
    publisher.start_worker()
    publisher.enqueue(event_type="queue.updated", payload={})
    publisher.close()
    assert publisher.dropped_events == 0
    assert "disabled" in publisher.endpoint
