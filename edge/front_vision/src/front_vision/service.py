"""FastAPI service: /health and /metrics around the inference pipeline."""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from .adp import AdpPublisher
from .capture import FrameSource
from .config import ENVELOPE_SCHEMA_PATH, FrontVisionConfig
from .pipeline import FrontVisionPipeline

logger = logging.getLogger("front_vision.service")

STARTED_AT = time.time()


def build_pipeline(
    config: FrontVisionConfig,
    publisher: Optional[AdpPublisher] = None,
    capture: Optional[FrameSource] = None,
) -> FrontVisionPipeline:
    """Wire capture, detector, emotion analyzer and pipeline together."""
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
    emotion_analyzer = None
    if config.emotion_enabled:
        from .emotion import EmotionAnalyzer

        emotion_analyzer = EmotionAnalyzer(config.yunet_model_path, config.face_confidence)
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
    return FrontVisionPipeline(config, publisher, capture, detector, emotion_analyzer)


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
            emotion_summary = dict(pipeline.last_emotion_summary)
            frames_inferred = pipeline.frames_inferred
            last_frame_at = pipeline.last_frame_at
        return {
            "current_count": pipeline.current_count,
            "frames_captured": capture.frames_captured,
            "frames_inferred": frames_inferred,
            "last_frame_at": last_frame_at,
            "detector_backend": pipeline.backend_name,
            "emotion_summary": emotion_summary,
            "queue_zone_id": config.queue_zone_id,
        }

    return app
