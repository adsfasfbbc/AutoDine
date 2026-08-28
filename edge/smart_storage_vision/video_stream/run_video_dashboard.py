from __future__ import annotations

import argparse
import sys
from pathlib import Path


VIDEO_ROOT = Path(__file__).resolve().parent
MODULE_ROOT = VIDEO_ROOT.parent
sys.path.insert(0, str(MODULE_ROOT))
sys.path.insert(0, str(MODULE_ROOT / "src"))

from video_stream.inference import VideoYoloTrackingAnalyzer
from video_stream.runtime import RoleSeparatedVideoRuntime, create_video_dashboard_app


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the AutoDine A dual-video browser dashboard")
    parser.add_argument("--inventory-video", type=Path, required=True)
    parser.add_argument("--security-video", type=Path, required=True)
    parser.add_argument(
        "--fruit-detector",
        type=Path,
        default=MODULE_ROOT / "models" / "fruit_detector_yolo26n_v1_best.pt",
    )
    parser.add_argument(
        "--person-detector",
        type=Path,
        default=MODULE_ROOT / "models" / "person_yolo26n_coco.pt",
    )
    parser.add_argument(
        "--quality-model",
        type=Path,
        default=MODULE_ROOT / "models" / "fruit_quality_yolo26_v2_best.pt",
    )
    parser.add_argument("--detection-confidence", type=float, default=0.25)
    parser.add_argument("--quality-confidence", type=float, default=0.7)
    parser.add_argument("--playback-rate", type=float, default=1.0)
    parser.add_argument("--tracking-iou", type=float, default=0.3)
    parser.add_argument("--tracking-max-missed", type=int, default=15)
    parser.add_argument("--no-loop", action="store_true", help="Stop each stream at EOF and retain its last frame")
    parser.add_argument(
        "--mock-unauthorized-rate",
        type=float,
        default=0.0,
        help="UI-only demo probability; disabled by default and never published to Core",
    )
    parser.add_argument("--mock-check-interval", type=float, default=8.0)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8091)
    args = parser.parse_args()

    for video_path in (args.inventory_video, args.security_video):
        if not video_path.is_file():
            raise FileNotFoundError(video_path)
    for model_path in (args.fruit_detector, args.person_detector, args.quality_model):
        if not model_path.is_file():
            raise FileNotFoundError(model_path)

    analyzer = VideoYoloTrackingAnalyzer(
        fruit_detector_path=args.fruit_detector,
        person_detector_path=args.person_detector,
        quality_model_path=args.quality_model,
        detection_confidence=args.detection_confidence,
        quality_confidence=args.quality_confidence,
        tracking_iou=args.tracking_iou,
        tracking_max_missed=args.tracking_max_missed,
    )
    runtime = RoleSeparatedVideoRuntime(
        analyzer=analyzer,
        inventory_video=args.inventory_video,
        security_video=args.security_video,
        loop=not args.no_loop,
        playback_rate=args.playback_rate,
        mock_unauthorized_rate=args.mock_unauthorized_rate,
        mock_check_interval_seconds=args.mock_check_interval,
    )
    app = create_video_dashboard_app(runtime, VIDEO_ROOT / "web" / "dashboard.html")

    print("VIDEO NOTICE: counts are cumulative unique tracks, not per-frame sums or line-crossing totals.")
    if args.mock_unauthorized_rate > 0:
        print("MOCK NOTICE: unauthorized-entry logs are random UI-only demos and are never published to Core.")
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        print("NETWORK NOTICE: dashboard has no authentication; expose it only on a trusted lab LAN.")

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
