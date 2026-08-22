"""Tests for the debug preview: / page and /preview.mjpeg MJPEG stream.

Uses stub detector/capture so no camera, GPU or model files are needed.
"""
from __future__ import annotations

import time

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from front_vision.adp import AdpPublisher
from front_vision.config import ENVELOPE_SCHEMA_PATH, FrontVisionConfig
from front_vision.pipeline import FrontVisionPipeline
from front_vision.service import create_app


class StubCapture:
    frames_captured = 1

    def __init__(self):
        self._frame = np.full((480, 640, 3), 40, dtype=np.uint8)

    def start(self):
        pass

    def stop(self):
        pass

    def latest(self):
        return self._frame

    def latest_shape(self):
        return (640, 480)


class StubDetector:
    backend_name = "stub"

    def detect_with_scores(self, frame):
        return [((10.0, 10.0, 100.0, 200.0), 0.9)]

    def detect(self, frame):
        return [b for b, _ in self.detect_with_scores(frame)]


def _make_app(preview_enabled: bool = True):
    config = FrontVisionConfig()
    config.preview_enabled = preview_enabled
    config.infer_every_n_frames = 1
    config.core_url = "http://core.test"
    publisher = AdpPublisher(
        core_url=config.core_url,
        schema_path=ENVELOPE_SCHEMA_PATH,
        retries=1,
        backoff_seconds=0.0,
        client=httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json={}))),
    )
    pipeline = FrontVisionPipeline(config, publisher, StubCapture(), StubDetector())
    app = create_app(config, pipeline=pipeline, capture=pipeline._capture)
    return app, pipeline


def _wait_for_preview(pipeline, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while pipeline.preview_jpeg() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    assert pipeline.preview_jpeg() is not None, "no annotated frame produced"


def test_root_returns_debug_html() -> None:
    app, pipeline = _make_app(preview_enabled=True)
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        assert "DEBUG PREVIEW" in resp.text
        assert "/preview.mjpeg" in resp.text


def test_mjpeg_stream_content_type_and_frames() -> None:
    # In-process clients (TestClient / ASGITransport) buffer infinite streams,
    # so exercise the MJPEG endpoint against a real uvicorn on a free port.
    import socket
    import threading

    import uvicorn

    app, pipeline = _make_app(preview_enabled=True)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10.0
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started
    try:
        _wait_for_preview(pipeline)
        with httpx.Client(trust_env=False) as client:
            with client.stream("GET", f"http://127.0.0.1:{port}/preview.mjpeg") as resp:
                assert resp.status_code == 200
                assert resp.headers["content-type"].startswith("multipart/x-mixed-replace")
                buf = b""
                for chunk in resp.iter_bytes(4096):
                    buf += chunk
                    if b"--frame" in buf and b"Content-Type: image/jpeg" in buf and b"\xff\xd8" in buf:
                        break
                assert b"--frame" in buf
                assert b"Content-Type: image/jpeg" in buf
                assert b"\xff\xd8" in buf  # JPEG SOI marker of the annotated frame
    finally:
        server.should_exit = True
        thread.join(timeout=5.0)


def test_preview_disabled_returns_404() -> None:
    app, pipeline = _make_app(preview_enabled=False)
    with TestClient(app) as client:
        resp = client.get("/preview.mjpeg")
        assert resp.status_code == 404
        page = client.get("/")
        assert page.status_code == 200
        assert "DEBUG PREVIEW" in page.text
        assert "/preview.mjpeg" not in page.text


def test_metrics_include_fps_and_preview_flag() -> None:
    app, pipeline = _make_app(preview_enabled=True)
    with TestClient(app) as client:
        _wait_for_preview(pipeline)
        m = client.get("/metrics").json()
        assert "inference_fps" in m
        assert m["preview_enabled"] is True
