from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the real YOLO fruit quality classifier")
    parser.add_argument("dataset", type=Path, help="Dataset root containing train/val/test class folders")
    parser.add_argument("--model", default="yolo26n-cls.pt")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--imgsz", type=int, default=224)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--project", type=Path, default=Path("edge/smart_storage_vision/output/training"))
    parser.add_argument("--name", default="fruit_quality_yolo26_v2")
    parser.add_argument("--resume", type=Path, help="Resume an interrupted run from its last.pt checkpoint")
    args = parser.parse_args()

    if args.resume:
        model = YOLO(str(args.resume.resolve()))
        model.train(resume=True)
    else:
        model = YOLO(args.model)
        model.train(
            data=str(args.dataset.resolve()),
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            workers=args.workers,
            device=0,
            seed=42,
            deterministic=True,
            patience=8,
            project=str(args.project.resolve()),
            name=args.name,
        )
    best = Path(model.trainer.best)
    YOLO(str(best)).val(
        data=str(args.dataset.resolve()),
        split="test",
        imgsz=args.imgsz,
        batch=args.batch,
        workers=args.workers,
        device=0,
        project=str(args.project.resolve()),
        name=f"{args.name}_test",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
