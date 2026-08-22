"""PySide6 desktop debug preview window for the front_vision edge service.

GUI mode (`--gui`) replaces the FastAPI service with a native window: the
left side shows the newest annotated frame from the pipeline (memory-only,
decoded from the same in-memory JPEG the MJPEG endpoint serves), the right
side shows live metrics. The Qt event loop runs on the main thread while
capture and inference stay on their background threads.
"""
from __future__ import annotations

import logging
import sys
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from .config import ENVELOPE_SCHEMA_PATH, FrontVisionConfig
from .pipeline import FrontVisionPipeline

logger = logging.getLogger("front_vision.gui")

WINDOW_TITLE = "AutoDine FrontVision - DEBUG"


class NullPublisher:
    """Drop-in AdpPublisher replacement for --no-publish local demos."""

    endpoint = "disabled (--no-publish)"
    dropped_events = 0

    def start_worker(self) -> None:
        pass

    def enqueue(self, **kwargs) -> None:
        pass

    def close(self) -> None:
        pass


class FrontVisionWindow(QMainWindow):
    """Desktop debug window: annotated live view + inference metrics."""

    def __init__(
        self,
        pipeline: FrontVisionPipeline,
        publisher=None,
        refresh_ms: int = 30,
    ) -> None:
        super().__init__()
        self._pipeline = pipeline
        self._publisher = publisher if publisher is not None else NullPublisher()

        self.setWindowTitle(WINDOW_TITLE)
        self.resize(980, 540)

        central = QWidget(self)
        layout = QHBoxLayout(central)

        # Left: annotated live frame.
        self._video_label = QLabel("waiting for frames...")
        self._video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video_label.setMinimumSize(640, 480)
        self._video_label.setStyleSheet("background: #000; color: #888;")
        layout.addWidget(self._video_label, stretch=1)

        # Right: metrics panel.
        panel = QVBoxLayout()
        self._count_label = QLabel("-")
        self._count_label.setStyleSheet("font-size: 48px; font-weight: 700; color: #4caf50;")
        panel.addWidget(QLabel("当前人数"))
        panel.addWidget(self._count_label)

        form = QFormLayout()
        self._backend_label = QLabel("-")
        self._fps_label = QLabel("-")
        self._publish_label = QLabel("-")
        self._publish_label.setWordWrap(True)
        form.addRow("检测后端", self._backend_label)
        form.addRow("推理 FPS", self._fps_label)
        form.addRow("Core 发布", self._publish_label)
        panel.addLayout(form)

        panel.addWidget(QLabel("情绪聚合（60s 滑窗）"))
        self._samples_label = QLabel("样本数: -")
        panel.addWidget(self._samples_label)
        self._emotion_bars: dict[str, tuple[str, QLabel, QProgressBar]] = {}
        for key, text, color in (
            ("positive_ratio", "positive", "#4caf50"),
            ("neutral_ratio", "neutral", "#9e9e9e"),
            ("negative_ratio", "negative", "#ef5350"),
        ):
            label = QLabel(f"{text} -")
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            bar.setStyleSheet(f"QProgressBar::chunk {{ background: {color}; }}")
            panel.addWidget(label)
            panel.addWidget(bar)
            self._emotion_bars[key] = (text, label, bar)
        panel.addStretch(1)

        right = QWidget()
        right.setLayout(panel)
        right.setFixedWidth(300)
        layout.addWidget(right)

        self.setCentralWidget(central)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(refresh_ms)

    def refresh(self) -> None:
        """Pull the newest annotated frame and metrics from the pipeline."""
        pipeline = self._pipeline

        jpeg = pipeline.preview_jpeg()
        if jpeg:
            image = QImage.fromData(jpeg)
            if not image.isNull():
                pixmap = QPixmap.fromImage(image).scaled(
                    self._video_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._video_label.setPixmap(pixmap)

        with pipeline._lock:
            summary = dict(pipeline.last_emotion_summary)
            count = pipeline.current_count
        self._count_label.setText(str(count))
        self._backend_label.setText(pipeline.backend_name)
        self._fps_label.setText(f"{pipeline.inference_fps:.1f}")
        self._publish_label.setText(
            f"{self._publisher.endpoint}\ndropped={self._publisher.dropped_events}"
        )
        self._samples_label.setText(f"样本数: {summary['sample_count']}")
        for key, (name, label, bar) in self._emotion_bars.items():
            pct = round((summary.get(key) or 0.0) * 100)
            label.setText(f"{name} {pct}%")
            bar.setValue(pct)


def run_gui(config: FrontVisionConfig, publish: bool = True) -> int:
    """Run capture + inference (+ optional publishing) with the desktop window."""
    import faulthandler

    from PySide6.QtWidgets import QApplication

    from .service import build_pipeline

    # Dump native tracebacks (e.g. access violations inside Qt/cv2) to stderr.
    faulthandler.enable()

    # The GUI reuses the in-memory annotated preview frames.
    config.preview_enabled = True

    publisher = None
    if publish:
        from .adp import AdpPublisher

        publisher = AdpPublisher(
            core_url=config.core_url,
            schema_path=ENVELOPE_SCHEMA_PATH,
            retries=config.publish_retries,
            backoff_seconds=config.publish_retry_backoff_seconds,
            timeout_seconds=config.publish_timeout_seconds,
        )
    pipeline = build_pipeline(config, publisher=publisher or NullPublisher())
    capture = pipeline._capture

    app = QApplication(sys.argv[:1])
    capture.start()
    pipeline.start()
    logger.info(
        "front_vision GUI started (source=%s, backend=%s, publish=%s)",
        config.source, pipeline.backend_name, publish,
    )

    window = FrontVisionWindow(pipeline, publisher or NullPublisher())

    def _cleanup() -> None:
        pipeline.stop()
        capture.stop()
        pipeline._publisher.close()
        logger.info("front_vision GUI stopped; camera released")

    app.aboutToQuit.connect(_cleanup)
    window.show()
    return app.exec()
