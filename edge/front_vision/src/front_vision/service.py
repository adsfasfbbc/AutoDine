"""FastAPI service: /health, /metrics and the MJPEG debug preview."""
from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse

from .adp import AdpPublisher
from .capture import FrameSource
from .config import ENVELOPE_SCHEMA_PATH, FrontVisionConfig
from .pipeline import FrontVisionPipeline

logger = logging.getLogger("front_vision.service")

STARTED_AT = time.time()

_DEBUG_PAGE_HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>front_vision debug</title>
<style>
  body { margin: 0; font-family: "Segoe UI", Arial, sans-serif; background: #14161a; color: #e8e8e8; }
  header { background: #b3261e; color: #fff; padding: 8px 16px; font-weight: 600; letter-spacing: 1px; }
  main { display: flex; gap: 16px; padding: 16px; align-items: flex-start; }
  .video { flex: 0 0 auto; }
  .video img { width: 640px; max-width: 100%; background: #000; border: 1px solid #333; }
  .panel { flex: 1 1 260px; background: #1d2026; border: 1px solid #333; border-radius: 6px; padding: 16px; }
  .panel h2 { margin-top: 0; font-size: 15px; color: #9ab; }
  .big { font-size: 56px; font-weight: 700; color: #4caf50; }
  dl { display: grid; grid-template-columns: auto 1fr; gap: 4px 12px; font-size: 14px; }
  dt { color: #889; } dd { margin: 0; font-family: Consolas, monospace; }
</style>
</head>
<body>
<header>DEBUG PREVIEW - 仅本机调试</header>
<main>
  <div class="video"><img src="/preview.mjpeg" alt="preview"></div>
  <div class="panel">
    <h2>实时指标</h2>
    <div class="big" id="count">-</div>
    <dl>
      <dt>推理后端</dt><dd id="backend">-</dd>
      <dt>推理 FPS</dt><dd id="fps">-</dd>
      <dt>采集帧数</dt><dd id="captured">-</dd>
    </dl>
  </div>
</main>
<script>
async function refresh() {
  try {
    const m = await (await fetch("/metrics")).json();
    document.getElementById("count").textContent = m.current_count;
    document.getElementById("backend").textContent = m.detector_backend;
    document.getElementById("fps").textContent = m.inference_fps;
    document.getElementById("captured").textContent = m.frames_captured;
  } catch (err) { /* service restarting */ }
}
refresh();
setInterval(refresh, 2000);
</script>
</body>
</html>
"""

_DEBUG_PAGE_DISABLED_HTML = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>front_vision debug</title></head>
<body style="font-family:sans-serif">
<h1>DEBUG PREVIEW - 仅本机调试</h1>
<p>预览已关闭（FV_PREVIEW_ENABLED=false / --no-preview）。指标仍可通过 <a href="/metrics">/metrics</a> 获取。</p>
</body></html>
"""


def build_pipeline(
    config: FrontVisionConfig,
    publisher: Optional[AdpPublisher] = None,
    capture: Optional[FrameSource] = None,
) -> FrontVisionPipeline:
    """Wire capture, detector and pipeline together."""
    from .people import PersonDetector

    onnx_path = config.yolo_model_path.replace(".pt", ".onnx")
    import os
    onnx_path = onnx_path if os.path.exists(onnx_path) else None

    detector = PersonDetector(
        model_path=config.yolo_model_path,
        onnx_model_path=onnx_path,
        backend=config.detector_backend,
        confidence=config.person_confidence,
    )
    publisher = publisher or AdpPublisher(
        core_url=config.core_url,
        schema_path=ENVELOPE_SCHEMA_PATH,
        retries=config.publish_retries,
        backoff_seconds=config.publish_retry_backoff_seconds,
        timeout_seconds=config.publish_timeout_seconds,
    )
    capture = capture or FrameSource(
        source=config.source,
        camera_index=config.camera_index,
        width=config.frame_width,
        height=config.frame_height,
    )
    return FrontVisionPipeline(config, publisher, capture, detector)


def create_app(
    config: Optional[FrontVisionConfig] = None,
    pipeline: Optional[FrontVisionPipeline] = None,
    capture: Optional[FrameSource] = None,
) -> FastAPI:
    config = config or FrontVisionConfig()
    if pipeline is None:
        pipeline = build_pipeline(config, capture=capture)
        capture = pipeline._capture  # the pipeline owns its capture source
    else:
        capture = capture or pipeline._capture

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        capture.start()
        pipeline.start()
        logger.info("front_vision service started (source=%s, backend=%s)", config.source, pipeline.backend_name)
        try:
            yield
        finally:
            pipeline.stop()
            capture.stop()
            logger.info("front_vision service stopped")

    app = FastAPI(title="AutoDine Front Vision", version="0.1.0", lifespan=lifespan)
    app.state.config = config
    app.state.pipeline = pipeline
    app.state.capture = capture

    @app.get("/health")
    def health() -> dict:
        frame = capture.latest_shape()
        return {
            "status": "ok" if frame is not None else "degraded",
            "module": "front_vision",
            "source": config.source,
            "capture_alive": frame is not None,
            "frame_size": {"width": frame[0], "height": frame[1]} if frame else None,
            "uptime_seconds": round(time.time() - STARTED_AT, 1),
        }

    @app.get("/metrics")
    def metrics() -> dict:
        with pipeline._lock:
            frames_inferred = pipeline.frames_inferred
            last_frame_at = pipeline.last_frame_at
        return {
            "current_count": pipeline.current_count,
            "frames_captured": capture.frames_captured,
            "frames_inferred": frames_inferred,
            "inference_fps": round(pipeline.inference_fps, 1),
            "last_frame_at": last_frame_at,
            "detector_backend": pipeline.backend_name,
            "queue_zone_id": config.queue_zone_id,
            "preview_enabled": config.preview_enabled,
        }

    @app.get("/", response_class=HTMLResponse)
    def debug_page() -> str:
        return _DEBUG_PAGE_HTML if config.preview_enabled else _DEBUG_PAGE_DISABLED_HTML

    @app.get("/preview.mjpeg")
    async def preview_mjpeg():
        if not config.preview_enabled:
            raise HTTPException(status_code=404, detail="preview disabled")

        async def stream():
            last_sent = None
            while True:
                data = pipeline.preview_jpeg()
                if data is None or data is last_sent:
                    await asyncio.sleep(0.05)
                    continue
                last_sent = data
                yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " \
                    + str(len(data)).encode() + b"\r\n\r\n" + data + b"\r\n"

        return StreamingResponse(stream(), media_type="multipart/x-mixed-replace; boundary=frame")

    return app
