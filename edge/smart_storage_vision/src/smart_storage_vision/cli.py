from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

from .backends import MockBackend
from .models import IngredientCalibration
from .pipeline import SmartStoragePipeline
from .publishers import publish_to_core, write_events
from .state import SnapshotStore


MODULE_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the AutoDine A-side SmartStorageVision prototype")
    parser.add_argument("--input", type=Path, default=MODULE_ROOT / "data" / "mock_scene.json")
    parser.add_argument("--output", type=Path, default=MODULE_ROOT / "output" / "demo_events.json")
    parser.add_argument("--display-file", type=Path, default=MODULE_ROOT / "output" / "display_status.json")
    parser.add_argument("--state-file", type=Path, default=MODULE_ROOT / "output" / "snapshot_state.json")
    parser.add_argument("--core-url", help="Optional AutoDineCore base URL")
    parser.add_argument("--authorized-task-id", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pipeline = SmartStoragePipeline(
        backend=MockBackend(),
        calibrations=[
            IngredientCalibration("lemon", "g", Decimal("120")),
            IngredientCalibration("tomato", "g", Decimal("100")),
        ],
        store_id="store-main",
        device_id="storage-cam-01",
        state_store=SnapshotStore(args.state_file),
    )
    observations, events = pipeline.analyze(args.input, authorized_task_ids=args.authorized_task_id)
    write_events(events, args.output)
    args.display_file.parent.mkdir(parents=True, exist_ok=True)
    args.display_file.write_text(
        json.dumps(
            {
                "module": "smart_storage_vision",
                "backend": pipeline.backend.name,
                "status": "ok",
                "items": [
                    {
                        "ingredient_id": item.ingredient_id,
                        "object_count": item.object_count,
                        "defective_count": item.defective_count,
                        "review_count": item.review_count,
                    }
                    for item in observations
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    results = publish_to_core(events, args.core_url) if args.core_url else []
    print(json.dumps({"events": len(events), "core_results": results, "output": str(args.output)}, ensure_ascii=False))
    return 0

