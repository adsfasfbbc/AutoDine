from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


DETECTION_CLASSES = ["apple", "banana", "grape", "orange", "pineapple", "watermelon"]
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass(frozen=True)
class QualityImage:
    path: Path
    label: str
    source: str
    sequence: int | None
    sha256: str


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_image(path: Path) -> None:
    with Image.open(path) as image:
        image.verify()


def audit_detection(source: Path, output: Path) -> dict:
    split_stats: dict[str, dict] = {}
    class_boxes: Counter[str] = Counter()
    source_ids: dict[str, set[str]] = {}
    errors: list[str] = []

    for split in ("train", "valid", "test"):
        image_dir = source / split / "images"
        label_dir = source / split / "labels"
        images = {path.stem: path for path in image_dir.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES}
        labels = {path.stem: path for path in label_dir.glob("*.txt")}
        missing_labels = sorted(images.keys() - labels.keys())
        missing_images = sorted(labels.keys() - images.keys())
        if missing_labels or missing_images:
            errors.append(
                f"{split}: missing_labels={len(missing_labels)}, missing_images={len(missing_images)}"
            )

        ids: set[str] = set()
        box_count = 0
        for stem, image_path in images.items():
            validate_image(image_path)
            ids.add(stem.split("_jpg.rf.", 1)[0])
            label_path = labels.get(stem)
            if label_path is None:
                continue
            lines = [line.strip() for line in label_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if not lines:
                errors.append(f"empty label file: {label_path}")
            for line_number, line in enumerate(lines, start=1):
                fields = line.split()
                if len(fields) != 5:
                    errors.append(f"invalid field count: {label_path}:{line_number}")
                    continue
                class_id = int(fields[0])
                values = [float(value) for value in fields[1:]]
                if class_id not in range(len(DETECTION_CLASSES)):
                    errors.append(f"invalid class id: {label_path}:{line_number}")
                    continue
                x, y, width, height = values
                if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < width <= 1 and 0 < height <= 1):
                    errors.append(f"invalid normalized box: {label_path}:{line_number}")
                    continue
                class_boxes[DETECTION_CLASSES[class_id]] += 1
                box_count += 1
        source_ids[split] = ids
        split_stats[split] = {
            "images": len(images),
            "labels": len(labels),
            "boxes": box_count,
            "source_ids": len(ids),
        }

    overlaps = {
        "train_valid": len(source_ids["train"] & source_ids["valid"]),
        "train_test": len(source_ids["train"] & source_ids["test"]),
        "valid_test": len(source_ids["valid"] & source_ids["test"]),
    }
    if any(overlaps.values()):
        errors.append(f"source-id split leakage: {overlaps}")
    if errors:
        raise ValueError("detection dataset audit failed:\n" + "\n".join(errors[:50]))

    yaml_path = output / "fruit_detection_v1.yaml"
    source_posix = source.resolve().as_posix()
    yaml_path.write_text(
        "\n".join(
            [
                f"path: '{source_posix}'",
                "train: train/images",
                "val: valid/images",
                "test: test/images",
                "names:",
                *[f"  {index}: {name}" for index, name in enumerate(DETECTION_CLASSES)],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "source": str(source.resolve()),
        "classes": DETECTION_CLASSES,
        "splits": split_stats,
        "boxes_by_class": dict(sorted(class_boxes.items())),
        "source_id_overlap": overlaps,
        "generated_yaml": str(yaml_path.resolve()),
        "license": "unverified_user_supplied_roboflow_export",
    }


def canonical_quality_label(directory_name: str) -> str:
    if directory_name.startswith("F_"):
        return f"fresh_{directory_name[2:].lower()}"
    if directory_name.startswith("S_"):
        return f"rotten_{directory_name[2:].lower()}"
    match = re.fullmatch(r"(Fresh|Rotten)([A-Za-z]+)", directory_name)
    if match:
        return f"{match.group(1).lower()}_{match.group(2).lower()}"
    raise ValueError(f"unsupported quality class directory: {directory_name}")


def numeric_sequence(path: Path) -> int | None:
    numbers = re.findall(r"\d+", path.stem)
    return int(numbers[-1]) if numbers else None


def collect_quality_images(root: Path, source_name: str) -> list[QualityImage]:
    records: list[QualityImage] = []
    for class_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        label = canonical_quality_label(class_dir.name)
        for path in sorted(class_dir.iterdir()):
            if path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            validate_image(path)
            records.append(
                QualityImage(
                    path=path,
                    label=label,
                    source=source_name,
                    sequence=numeric_sequence(path),
                    sha256=file_sha256(path),
                )
            )
    return records


def assign_grouped_splits(records: list[QualityImage], seed: int) -> dict[str, list[QualityImage]]:
    by_label: dict[str, list[QualityImage]] = defaultdict(list)
    for record in records:
        by_label[record.label].append(record)

    result = {"train": [], "val": [], "test": []}
    rng = random.Random(seed)
    for label, items in sorted(by_label.items()):
        groups: dict[tuple[str, int | str], list[QualityImage]] = defaultdict(list)
        for item in items:
            group_id: int | str = item.sequence // 20 if item.sequence is not None else item.sha256
            groups[(item.source, group_id)].append(item)
        grouped = list(groups.values())
        rng.shuffle(grouped)
        targets = {
            "train": len(items) * 0.70,
            "val": len(items) * 0.15,
            "test": len(items) * 0.15,
        }
        counts = Counter()
        for group in grouped:
            split = max(targets, key=lambda name: targets[name] - counts[name])
            result[split].extend(group)
            counts[split] += len(group)
    return result


def link_or_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def prepare_quality(fruit16k: Path, original_image: Path, destination: Path, seed: int) -> dict:
    records = collect_quality_images(fruit16k, "fruit16k")
    records.extend(collect_quality_images(original_image, "original_image"))

    by_hash: dict[str, QualityImage] = {}
    duplicate_count = 0
    conflicts: list[tuple[str, str, str]] = []
    for record in records:
        previous = by_hash.get(record.sha256)
        if previous is None:
            by_hash[record.sha256] = record
        elif previous.label != record.label:
            conflicts.append((record.sha256, previous.label, record.label))
        else:
            duplicate_count += 1
    if conflicts:
        raise ValueError(f"quality dataset has {len(conflicts)} exact-image label conflicts")

    unique_records = list(by_hash.values())
    splits = assign_grouped_splits(unique_records, seed)
    for split, items in splits.items():
        for item in items:
            filename = f"{item.source}_{item.sha256[:16]}{item.path.suffix.lower()}"
            link_or_copy(item.path, destination / split / item.label / filename)

    counts = {
        split: dict(sorted(Counter(item.label for item in items).items()))
        for split, items in splits.items()
    }
    return {
        "sources": {
            "fruit16k": str(fruit16k.resolve()),
            "original_image": str(original_image.resolve()),
        },
        "raw_images": len(records),
        "unique_exact_sha256_images": len(unique_records),
        "removed_exact_duplicates": duplicate_count,
        "exact_label_conflicts": len(conflicts),
        "split_method": "per-label, per-source numeric-sequence groups of 20; seed fixed; exact duplicates removed",
        "seed": seed,
        "classes": sorted({record.label for record in unique_records}),
        "counts": counts,
        "license": {
            "fruit16k": "CC_BY_4.0",
            "original_image": "unverified_user_supplied",
        },
        "near_duplicate_limit": "not exhaustively clustered; sequence grouping reduces adjacent-frame leakage",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit and prepare AutoDine fruit training datasets")
    parser.add_argument("--detection", type=Path, required=True)
    parser.add_argument("--fruit16k", type=Path, required=True)
    parser.add_argument("--original-image", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=False)
    report = {
        "detection": audit_detection(args.detection, args.output),
        "quality": prepare_quality(
            args.fruit16k,
            args.original_image,
            args.output / "fruit_quality_v2",
            args.seed,
        ),
    }
    (args.output / "dataset_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
