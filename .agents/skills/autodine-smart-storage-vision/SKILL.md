---
name: autodine-smart-storage-vision
description: Build, test, and integrate AutoDine module A (SmartStorageVision) for storage-camera ingredient counting, quality screening, unexplained-loss alarms, ADP v1 events, and Jetson-ready deployment. Use for work under edge/smart_storage_vision or its A-side contracts and fixtures; do not use for implementing modules B-F.
---

# AutoDine SmartStorageVision (A)

Keep module A independently runnable and compatible with the current AutoDine monorepo.

## Start every update

1. Read the repository status and current tree. Fetch/pull the configured `origin` only when the user authorized synchronization; never discard local work.
2. Read `contracts/adp/v1/envelope.schema.json`, the Core event schemas/handlers, `data/seed/catalog.json`, and [references/a-module-contract.md](references/a-module-contract.md).
3. Treat the repository contracts as the integration truth when they differ from old examples. Preserve unrelated work in modules B-F.

## Engineering rules

- Keep this chain demonstrable: real or Mock frame -> detection/count/quality screening -> ADP 1.0 output -> AutoDineCore acceptance.
- Use CountGD++ as the preferred open-world counting research backend. Keep the backend replaceable because its 1.25 GB checkpoint, CUDA extensions, and Linux build are not a reliable default on every workstation or Jetson.
- Use a lightweight trained detector/classifier (normally YOLO) for deterministic defect screening. Use VLM only to review low-confidence or conflicting cases; do not make network VLM access a hard dependency of counting.
- Keep the deterministic Mock backend working without GPU, camera, model weights, or network. Never claim the real model was trained or validated when only Mock tests ran.
- Whenever Mock input, Mock inference, simulated hardware, placeholder adapters, or hard-coded fixtures are used, say so plainly and prominently; never conceal, soften, or imply that they are real model or hardware results.
- Convert object counts to inventory units only through explicit per-ingredient calibration. Do not infer grams or millilitres directly from a bounding-box count.
- A owns RTSP/frame ingestion, visual inference, zone tracking, observations, and A-side ADP publication. Core owns business inventory/reservations/BOM/menu state. HardwareHub owns device control. DineWeb owns final UI.
- Emit exact snake_case ADP envelopes with UTC/ISO 8601 timestamps, idempotent event IDs, trace IDs, store/device identity, and only payload fields accepted by Core.
- Never overwrite Core-owned `reserved_quantity`. For unexplained decreases, compare stable snapshots and emit an alarm only when there is no authorized production task reference.
- Do not commit datasets, checkpoints, credentials, RTSP secrets, generated state, or annotated images. Record dataset license, version, source, split, and hashes.

## Verification and handoff

- Run A unit tests and the generated-event/Core integration test. Run the repository suite when shared contracts or root configuration change.
- Report separately what was verified with Mock, local model inference, RTSP hardware, Jetson, and Core.
- Every delivery to the user must explicitly state: what was completed; what was not completed; why each missing item was not completed; what should be done next; and concrete instructions for how to do the next step.
- After tests pass, commit and push only when authorized. Before pushing, re-check `origin`, branch, diff, and upstream changes; never force-push.
