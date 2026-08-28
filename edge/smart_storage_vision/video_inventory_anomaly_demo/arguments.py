from __future__ import annotations

import argparse
from pathlib import Path


def add_runtime_arguments(parser: argparse.ArgumentParser, *, module_root: Path, demo_root: Path) -> None:
    parser.add_argument("--inventory-video", type=Path, required=True, help="Video used only for six-class fruit detection")
    parser.add_argument("--security-video", type=Path, required=True, help="Video used only for person detection")
    parser.add_argument(
        "--fruit-detector",
        type=Path,
        default=module_root / "models" / "fruit_detector_yolo26n_v1_best.pt",
    )
    parser.add_argument(
        "--person-detector",
        type=Path,
        default=module_root / "models" / "person_yolo26n_coco.pt",
    )
    parser.add_argument(
        "--quality-model",
        type=Path,
        default=module_root / "models" / "fruit_quality_yolo26_v2_best.pt",
    )
    parser.add_argument(
        "--inventory-fixture",
        type=Path,
        default=demo_root / "fixtures" / "inventory_demo_v1.json",
    )
    parser.add_argument("--fruit-confidence", type=float, default=0.5)
    parser.add_argument("--person-confidence", type=float, default=0.25)
    parser.add_argument("--quality-confidence", type=float, default=0.7)
    parser.add_argument("--tracking-iou", type=float, default=0.3)
    parser.add_argument("--tracking-max-missed", type=int, default=15)
    parser.add_argument("--playback-rate", type=float, default=1.0)
    parser.add_argument("--loop", action="store_true", help="Replay both videos; cumulative vision counts remain frozen after pass one")
    parser.add_argument("--disable-demo-events", action="store_true", help="Keep fixture inventory fixed and disable authorization demo alerts")
    parser.add_argument("--allow-cpu", action="store_true", help="Allow explicit CPU fallback when CUDA is unavailable")


def runtime_kwargs(args) -> dict:
    return {
        "inventory_video": args.inventory_video,
        "security_video": args.security_video,
        "fruit_detector": args.fruit_detector,
        "person_detector": args.person_detector,
        "quality_model": args.quality_model,
        "fixture_path": args.inventory_fixture,
        "fruit_confidence": args.fruit_confidence,
        "person_confidence": args.person_confidence,
        "quality_confidence": args.quality_confidence,
        "tracking_iou": args.tracking_iou,
        "tracking_max_missed": args.tracking_max_missed,
        "playback_rate": args.playback_rate,
        "loop": args.loop,
        "demo_events_enabled": not args.disable_demo_events,
        "allow_cpu": args.allow_cpu,
    }
