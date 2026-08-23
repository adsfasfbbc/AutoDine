"""Configuration for the M02 front_vision edge service.

All values can be overridden via environment variables (prefix FV_)
or CLI flags in main.py. Defaults are tuned for the in-store dev setup:
a single USB/DirectShow camera at index 0, 640x480, Core on localhost:8000.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# config.py lives in src/front_vision/, so edge/front_vision/ is two levels up.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = PROJECT_ROOT / "models"
# contracts/ lives at the repository root, three levels above edge/front_vision.
REPO_ROOT = PROJECT_ROOT.parents[1]
ENVELOPE_SCHEMA_PATH = REPO_ROOT / "contracts" / "adp" / "v1" / "envelope.schema.json"


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw not in (None, "") else default


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw not in (None, "") else default


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw in (None, ""):
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class FrontVisionConfig:
    """Runtime settings for the front_vision service."""

    # Capture
    camera_index: int = field(default_factory=lambda: _int_env("FV_CAMERA_INDEX", 0))
    # "camera" for a live device, or a path to a video file (looped).
    source: str = field(default_factory=lambda: os.getenv("FV_SOURCE", "camera"))
    frame_width: int = field(default_factory=lambda: _int_env("FV_FRAME_WIDTH", 640))
    frame_height: int = field(default_factory=lambda: _int_env("FV_FRAME_HEIGHT", 480))

    # Core integration
    core_url: str = field(default_factory=lambda: os.getenv("FV_CORE_URL", "http://localhost:8000"))
    store_id: str = field(default_factory=lambda: os.getenv("FV_STORE_ID", "store-main"))
    device_id: str = field(default_factory=lambda: os.getenv("FV_DEVICE_ID", "front-cam-01"))
    queue_zone_id: str = field(default_factory=lambda: os.getenv("FV_QUEUE_ZONE_ID", "front-queue"))

    # Inference
    # "auto" prefers the torch/CUDA backend and falls back to onnxruntime.
    detector_backend: str = field(default_factory=lambda: os.getenv("FV_DETECTOR_BACKEND", "auto"))
    person_confidence: float = field(default_factory=lambda: _float_env("FV_PERSON_CONFIDENCE", 0.4))
    # Run heavy inference every Nth captured frame to keep CPU/GPU load sane.
    infer_every_n_frames: int = field(default_factory=lambda: _int_env("FV_INFER_EVERY_N_FRAMES", 5))
    # In-browser MJPEG debug preview (annotated frames, memory-only).
    preview_enabled: bool = field(default_factory=lambda: _bool_env("FV_PREVIEW_ENABLED", True))

    # Queue counting
    # ROI as normalized (x, y, w, h); v1 default covers the full frame.
    queue_roi: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
    smooth_window_seconds: float = field(default_factory=lambda: _float_env("FV_SMOOTH_WINDOW_S", 3.0))
    queue_heartbeat_seconds: float = field(default_factory=lambda: _float_env("FV_QUEUE_HEARTBEAT_S", 10.0))

    # HTTP publishing
    publish_retries: int = field(default_factory=lambda: _int_env("FV_PUBLISH_RETRIES", 3))
    publish_retry_backoff_seconds: float = field(default_factory=lambda: _float_env("FV_PUBLISH_BACKOFF_S", 0.5))
    publish_timeout_seconds: float = field(default_factory=lambda: _float_env("FV_PUBLISH_TIMEOUT_S", 5.0))

    # Service
    host: str = field(default_factory=lambda: os.getenv("FV_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _int_env("FV_PORT", 5060))

    yolo_model_path: str = field(default_factory=lambda: str(MODELS_DIR / "yolo11n.pt"))

    # Safety / conflict detection (vision pose + acoustic arousal fusion).
    # A vision.front.safety event is published only when BOTH modalities fire
    # within a ±3s window; single-modality cues are debug-logged only.
    safety_enabled: bool = field(default_factory=lambda: _bool_env("FV_SAFETY_ENABLED", True))
    safety_zone_id: str = field(default_factory=lambda: os.getenv("FV_SAFETY_ZONE_ID", "front-hall"))
    yolo_pose_model_path: str = field(default_factory=lambda: str(MODELS_DIR / "yolo11n-pose.pt"))
    safety_pose_confidence: float = field(default_factory=lambda: _float_env("FV_SAFETY_POSE_CONFIDENCE", 0.3))
    safety_vision_window_seconds: float = field(default_factory=lambda: _float_env("FV_SAFETY_VISION_WINDOW_S", 2.0))
    safety_vision_score_threshold: float = field(default_factory=lambda: _float_env("FV_SAFETY_VISION_THRESHOLD", 0.6))
    safety_vision_hysteresis_seconds: float = field(default_factory=lambda: _float_env("FV_SAFETY_VISION_HYSTERESIS_S", 2.0))
    # Acoustic channel: physical features only (loudness/F0/flux/onsets); raw
    # PCM is kept in a bounded 2s in-memory ring buffer, never persisted.
    audio_enabled: bool = field(default_factory=lambda: _bool_env("FV_AUDIO_ENABLED", True))
    audio_device: str = field(default_factory=lambda: os.getenv("FV_AUDIO_DEVICE", ""))
    audio_sample_rate: int = field(default_factory=lambda: _int_env("FV_AUDIO_SAMPLE_RATE", 16000))
    safety_audio_score_threshold: float = field(default_factory=lambda: _float_env("FV_SAFETY_AUDIO_THRESHOLD", 0.6))
    safety_audio_baseline_alpha: float = field(default_factory=lambda: _float_env("FV_SAFETY_AUDIO_BASELINE_ALPHA", 0.02))
    # Fusion timing.
    safety_fusion_window_seconds: float = field(default_factory=lambda: _float_env("FV_SAFETY_FUSION_WINDOW_S", 3.0))
    safety_cooldown_seconds: float = field(default_factory=lambda: _float_env("FV_SAFETY_COOLDOWN_S", 30.0))
    safety_critical_after_seconds: float = field(default_factory=lambda: _float_env("FV_SAFETY_CRITICAL_AFTER_S", 10.0))
    # Inject a deterministic dual-modality pattern for demos (--simulate-safety).
    simulate_safety: bool = False

    # Fire detection (YOLO flame vision + Modbus flame sensor fusion).
    # A vision.front.fire event is published only when BOTH channels fire
    # within a ±3s window; single-channel cues are debug-logged only.
    fire_enabled: bool = field(default_factory=lambda: _bool_env("FV_FIRE_ENABLED", True))
    fire_zone_id: str = field(default_factory=lambda: os.getenv("FV_FIRE_ZONE_ID", "front-hall"))
    fire_model_path: str = field(
        default_factory=lambda: os.getenv("FV_FIRE_MODEL_PATH", str(MODELS_DIR / "fire.pt"))
    )
    fire_confidence: float = field(default_factory=lambda: _float_env("FV_FIRE_CONFIDENCE", 0.25))
    # Flame inference is throttled again on top of FV_INFER_EVERY_N_FRAMES:
    # the model runs on every Nth pipeline inference frame.
    fire_infer_every_n_frames: int = field(default_factory=lambda: _int_env("FV_FIRE_INFER_EVERY_N_FRAMES", 5))
    # Modbus flame sensor channel (pyserial); a port that fails to open only
    # disables this channel ("sensor never fires"), never crashes the service.
    fire_sensor_enabled: bool = field(default_factory=lambda: _bool_env("FV_FIRE_SENSOR_ENABLED", True))
    # Empty = platform default (COM3 on Windows, /dev/ttyUSB0 on Linux).
    fire_sensor_port: str = field(default_factory=lambda: os.getenv("FV_FIRE_SENSOR_PORT", ""))
    fire_sensor_baudrate: int = field(default_factory=lambda: _int_env("FV_FIRE_SENSOR_BAUDRATE", 9600))
    fire_sensor_poll_seconds: float = field(default_factory=lambda: _float_env("FV_FIRE_SENSOR_POLL_S", 0.1))
    fire_sensor_timeout_seconds: float = field(default_factory=lambda: _float_env("FV_FIRE_SENSOR_TIMEOUT_S", 0.5))
    # Fusion timing.
    fire_fusion_window_seconds: float = field(default_factory=lambda: _float_env("FV_FIRE_FUSION_WINDOW_S", 3.0))
    fire_cooldown_seconds: float = field(default_factory=lambda: _float_env("FV_FIRE_COOLDOWN_S", 30.0))
    fire_critical_after_seconds: float = field(default_factory=lambda: _float_env("FV_FIRE_CRITICAL_AFTER_S", 10.0))
    # Inject a deterministic dual-channel pattern for demos (--simulate-fire).
    simulate_fire: bool = False


def is_port_free(host: str, port: int) -> bool:
    """Return True if nothing is listening on host:port (IPv4)."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) != 0
