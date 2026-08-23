from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create deterministic FRUIT-16K YOLO classification splits")
    parser.add_argument("source", type=Path, help="FRUIT-16K directory containing F_* and S_* classes")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    classes = sorted(path for path in args.source.iterdir() if path.is_dir())
    for class_dir in classes:
        images = sorted(path for path in class_dir.iterdir() if path.is_file())
        rng.shuffle(images)
        train_end = int(len(images) * 0.70)
        val_end = int(len(images) * 0.85)
        for split, items in (
            ("train", images[:train_end]),
            ("val", images[train_end:val_end]),
            ("test", images[val_end:]),
        ):
            target = args.destination / split / class_dir.name
            target.mkdir(parents=True, exist_ok=True)
            for image in items:
                shutil.copy2(image, target / image.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
