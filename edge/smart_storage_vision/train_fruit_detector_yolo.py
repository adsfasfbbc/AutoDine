from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the real YOLO26n six-class fruit detector")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--model", default="yolo26n.pt")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=12)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--project", type=Path, default=Path("edge/smart_storage_vision/output/training"))
    parser.add_argument("--name", default="fruit_detector_yolo26n_v1")
    args = parser.parse_args()

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
        patience=10,
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
