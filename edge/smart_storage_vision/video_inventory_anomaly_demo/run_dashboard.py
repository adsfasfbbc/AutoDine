from __future__ import annotations

import argparse
import sys
from pathlib import Path


DEMO_ROOT = Path(__file__).resolve().parent
MODULE_ROOT = DEMO_ROOT.parent
sys.path.insert(0, str(MODULE_ROOT))
sys.path.insert(0, str(MODULE_ROOT / "src"))

from video_inventory_anomaly_demo.arguments import add_runtime_arguments, runtime_kwargs
from video_inventory_anomaly_demo.bootstrap import build_runtime
from video_inventory_anomaly_demo.runtime import create_dashboard_app


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the isolated AutoDine inventory anomaly video dashboard")
    add_runtime_arguments(parser, module_root=MODULE_ROOT, demo_root=DEMO_ROOT)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8092)
    args = parser.parse_args()

    runtime = build_runtime(**runtime_kwargs(args))
    app = create_dashboard_app(runtime, DEMO_ROOT / "web" / "dashboard.html")

    print(f"INFERENCE DEVICE: {runtime.analyzer.device}")
    print("DATA NOTICE: only six fruit classes, fruit quality and person detections are model outputs.")
    print("DATA NOTICE: the 67-item inventory and permission decisions are demonstration data and are not published to Core.")
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        print("NETWORK NOTICE: this diagnostic dashboard has no authentication; use only on a trusted lab LAN.")

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
