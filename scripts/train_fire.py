"""Train the front_vision flame detection model (fire.pt).

Fine-tunes a YOLO26n pretrained backbone on an external flame dataset and
exports ONNX for the onnxruntime fallback backend. The dataset is NOT in this
repository — point --data at a YOLO-format data.yaml on your machine.

Usage (on a GPU host, e.g. RTX 50xx needs torch cu128):
    pip install ultralytics
    python scripts/train_fire.py --data /path/to/fire_dataset/data.yaml
    python scripts/train_fire.py --data data.yaml --model yolo26n.pt --epochs 100

After training, copy runs/detect/<name>/weights/best.pt to
edge/front_vision/models/fire.pt (that directory is gitignored — never commit
model weights), and best.onnx next to it for the fallback backend.
"""
from __future__ import annotations

import argparse


def main() -> None:
    from ultralytics import YOLO  # type: ignore

    parser = argparse.ArgumentParser(description="Fine-tune the front_vision flame detector")
    parser.add_argument("--data", required=True, help="path to the flame dataset data.yaml (external)")
    parser.add_argument("--model", default="yolo26n.pt", help="pretrained backbone weights")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--name", default="fire_train")
    args = parser.parse_args()

    model = YOLO(args.model)  # pretrained backbone, fine-tuned below
    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        name=args.name,
        # Small-dataset augmentation: mosaic is on by default; copy_paste helps
        # single-class small targets.
        copy_paste=0.1,
        fliplr=0.5,
        patience=20,  # early stop against overfitting
    )

    # Evaluate on the test split.
    best = YOLO(f"runs/detect/{args.name}/weights/best.pt")
    print(best.val(data=args.data, split="test"))

    # Export ONNX for the onnxruntime fallback backend of FireDetector.
    best.export(format="onnx", imgsz=args.imgsz, opset=12, simplify=True)
    print(f"exported: runs/detect/{args.name}/weights/best.onnx")


if __name__ == "__main__":
    main()
