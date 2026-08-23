# SmartStorageVision (module A)

Initial deliverable: a deterministic, dependency-light prototype that turns a Mock storage scene into ADP v1 events accepted by AutoDineCore. It also contains the stable backend interface for CountGD++/YOLO and the state comparison needed for unexplained inventory-loss alarms.

Run from the repository root:

```bash
python edge/smart_storage_vision/run_demo.py
python -m pytest -q edge/smart_storage_vision/tests
```

The demo writes `output/demo_events.json`, `output/display_status.json`, and `output/snapshot_state.json` below this module. To post Core-consumable events directly, add `--core-url http://localhost:8000`.

The first prototype deliberately uses a Mock backend. CountGD++ requires a separate Linux/CUDA environment and a 1.25 GB checkpoint; it is the preferred counting experiment, not an undeclared runtime dependency. See [technical prototype](../../docs/a-smart-storage-vision-prototype.md) and [dataset manifest](data/datasets.yaml).

Hardware ownership is explicit: A reads camera frames and produces observations; HardwareHub owns camera/device health and display control; DineWeb owns the final dashboard. A can feed a local status file to support a single-machine Zeuslap HDMI demonstration without coupling to either module.
