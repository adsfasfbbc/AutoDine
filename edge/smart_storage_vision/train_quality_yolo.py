from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the real YOLO fruit quality classifier")
    parser.add_argument("dataset", type=Path, help="Dataset root containing train/val/test class folders")
    parser.add_argument("--model", default="yolo11n-cls.pt")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--imgsz", type=int, default=224)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--project", type=Path, default=Path("edge/smart_storage_vision/output/training"))
    args = parser.parse_args()

    model = YOLO(args.model)
    model.train(
        data=str(args.dataset.resolve()),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=0,
        project=str(args.project.resolve()),
        name="fruit_quality_yolo",
    )
    best = Path(model.trainer.best)
    YOLO(str(best)).val(
        data=str(args.dataset.resolve()),
        split="test",
        imgsz=args.imgsz,
        batch=args.batch,
        device=0,
        project=str(args.project.resolve()),
        name="fruit_quality_yolo_test",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
