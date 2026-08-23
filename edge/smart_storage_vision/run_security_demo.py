from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4


MODULE_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(MODULE_ROOT / "src"))

from smart_storage_vision.security import (
    UltralyticsPersonDetector,
    evaluate_security,
    make_unauthorized_entry_event,
)


def _roi(value: str) -> tuple[float, float, float, float]:
    parts = tuple(float(item) for item in value.split(","))
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("ROI must be x1,y1,x2,y2 in normalized coordinates")
    return parts


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real YOLO person detection for storage-door security")
    parser.add_argument("source", type=Path)
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--roi", type=_roi, default=(0.0, 0.0, 1.0, 1.0))
    parser.add_argument("--door-open", action="store_true")
    parser.add_argument("--authorized", action="store_true")
    parser.add_argument("--zone-id", default="storage-door")
    parser.add_argument("--output", type=Path, default=MODULE_ROOT / "output" / "security_demo.json")
    args = parser.parse_args()

    detections = UltralyticsPersonDetector(args.model).detect(args.source)
    observation = evaluate_security(
        detections,
        doorway_roi=args.roi,
        door_open=args.door_open,
        authorization_present=args.authorized,
        zone_id=args.zone_id,
    )
    event = make_unauthorized_entry_event(
        observation,
        trace_id="security-" + uuid4().hex,
        store_id="store-main",
        device_id="storage-cam-01",
    )
    result = {
        "inference_backend": "ultralytics_yolo11n",
        "door_state_source": "command_line_demo",
        "observation": observation.to_dict(),
        "event": event,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

