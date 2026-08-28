from __future__ import annotations

from pathlib import Path

from video_stream.inference import VideoYoloTrackingAnalyzer

from .inventory import DemoInventoryProvider, InventoryAnomalyDetector
from .runtime import InventoryAnomalyVideoRuntime
from .vision import RoleConfidenceAnalyzer


def build_runtime(
    *,
    inventory_video: Path,
    security_video: Path,
    fruit_detector: Path,
    person_detector: Path,
    quality_model: Path,
    fixture_path: Path,
    fruit_confidence: float,
    person_confidence: float,
    quality_confidence: float,
    tracking_iou: float,
    tracking_max_missed: int,
    playback_rate: float,
    loop: bool,
    demo_events_enabled: bool,
    allow_cpu: bool,
) -> InventoryAnomalyVideoRuntime:
    for video_path in (inventory_video, security_video):
        if not video_path.is_file():
            raise FileNotFoundError(video_path)
    for model_path in (fruit_detector, person_detector, quality_model):
        if not model_path.is_file():
            raise FileNotFoundError(model_path)
    if not fixture_path.is_file():
        raise FileNotFoundError(fixture_path)

    shared_analyzer = VideoYoloTrackingAnalyzer(
        fruit_detector_path=fruit_detector,
        person_detector_path=person_detector,
        quality_model_path=quality_model,
        detection_confidence=fruit_confidence,
        quality_confidence=quality_confidence,
        tracking_iou=tracking_iou,
        tracking_max_missed=tracking_max_missed,
    )
    if shared_analyzer.device != 0 and not allow_cpu:
        raise RuntimeError("CUDA is unavailable; pass --allow-cpu only when CPU inference is intentional")
    analyzer = RoleConfidenceAnalyzer(
        shared_analyzer,
        fruit_confidence=fruit_confidence,
        person_confidence=person_confidence,
    )

    provider = DemoInventoryProvider(fixture_path, scenario_enabled=demo_events_enabled)
    detector = InventoryAnomalyDetector()
    return InventoryAnomalyVideoRuntime(
        analyzer=analyzer,
        inventory_provider=provider,
        anomaly_detector=detector,
        inventory_video=inventory_video,
        security_video=security_video,
        loop=loop,
        playback_rate=playback_rate,
        demo_events_enabled=demo_events_enabled,
    )
