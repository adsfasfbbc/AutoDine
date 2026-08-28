from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


DEMO_ROOT = Path(__file__).resolve().parent
MODULE_ROOT = DEMO_ROOT.parent
sys.path.insert(0, str(MODULE_ROOT))
sys.path.insert(0, str(MODULE_ROOT / "src"))

from video_inventory_anomaly_demo.arguments import add_runtime_arguments, runtime_kwargs
from video_inventory_anomaly_demo.bootstrap import build_runtime


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the isolated AutoDine inventory anomaly pipeline without a web UI")
    add_runtime_arguments(parser, module_root=MODULE_ROOT, demo_root=DEMO_ROOT)
    args = parser.parse_args()

    runtime = build_runtime(**runtime_kwargs(args))
    emit(
        {
            "event_type": "runtime.started",
            "device": runtime.analyzer.device,
            "simulated_inventory": True,
            "published_to_core": False,
        }
    )
    runtime.start()
    try:
        while not runtime.is_finished():
            for event in runtime.drain_events():
                emit(event)
            time.sleep(0.1)
        for event in runtime.drain_events():
            emit(event)
        snapshot = runtime.snapshot()
        emit(
            {
                "event_type": "runtime.completed",
                "runtime_error": snapshot["runtime_error"],
                "vision_counts": snapshot["vision_counts"],
                "security_counts": snapshot["security_counts"],
                "alert_count": len(snapshot["alerts"]),
            }
        )
        return 1 if snapshot["runtime_error"] else 0
    except KeyboardInterrupt:
        emit({"event_type": "runtime.stopped", "reason": "keyboard_interrupt"})
        return 130
    finally:
        runtime.stop()


if __name__ == "__main__":
    raise SystemExit(main())
