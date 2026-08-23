from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(MODULE_ROOT / "src"))

from smart_storage_vision.backends import UltralyticsFruitBackend
from smart_storage_vision.models import IngredientCalibration
from smart_storage_vision.pipeline import SmartStoragePipeline
from smart_storage_vision.publishers import publish_to_core, write_events


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real YOLO fruit counting and quality inference")
    parser.add_argument("source", type=Path)
    parser.add_argument("--detector", default="yolo11n.pt")
    parser.add_argument("--quality-model", help="Trained YOLO classification checkpoint; omitted means review, not good")
    parser.add_argument("--location-id", default="storage-main")
    parser.add_argument("--quantity-per-object", type=Decimal, default=Decimal("1"))
    parser.add_argument("--unit", default="pcs")
    parser.add_argument("--core-url")
    parser.add_argument("--output", type=Path, default=MODULE_ROOT / "output" / "yolo_inventory_events.json")
    args = parser.parse_args()

    backend = UltralyticsFruitBackend(
        args.detector,
        quality_model_path=args.quality_model,
        location_id=args.location_id,
    )
    pipeline = SmartStoragePipeline(
        backend=backend,
        calibrations=[
            IngredientCalibration(name, args.unit, args.quantity_per_object)
            for name in ("apple", "banana", "orange")
        ],
        store_id="store-main",
        device_id="storage-cam-01",
    )
    observations, events = pipeline.analyze(args.source)
    write_events(events, args.output)
    core_results = publish_to_core(events, args.core_url) if args.core_url else []
    print(
        json.dumps(
            {
                "inference_backend": backend.name,
                "detector": args.detector,
                "quality_model": args.quality_model,
                "quality_without_model": "review",
                "observations": [item.__dict__ for item in observations],
                "events": len(events),
                "core_results": core_results,
                "output": str(args.output),
            },
            ensure_ascii=False,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
