# A module contract

## Required outcome

Module A covers back-of-house ingredient recognition/counting, storage-zone tracking, spoilage/mould screening with optional VLM review, and detection of inventory decreases without a legal production task. Acceptance is not model inference alone: input, processing, ADP output, and Core receipt must all work.

## Stable integration boundary

- Input: Mock scene JSON first; image/video file and RTSP adapters next.
- Business outputs consumed by Core:
  - `inventory.detected`: `ingredient_id`, `location_id`, `physical_quantity`, `unit`, optional `defective_quantity`.
  - `quality.abnormal`: `ingredient_id`, `location_id`, `defective_quantity`.
- Diagnostic output: `vision.storage.detected`.
- Alarm output: `alarm.opened` with reason, previous/current quantities, unit, location, and task references.
- Core reservations are never vision-owned.

## Model decision

CountGD++ is the primary open-world count/detection experiment and is evaluated on fruit scenes. A compact YOLO model is the practical Jetson fallback and quality-screening model. Faster R-CNN is a benchmark only when an accuracy comparison justifies its slower deployment profile.

## Data decision

- Counting/evaluation: OmniCount-191 fruit subset (OpenRAIL++), also used by the official CountGD++ evaluation.
- Quality pretraining: FRUIT-16K spoiled/fresh dataset (CC BY 4.0; 16,000 images, eight fruit types).
- Domain validation: collect and annotate a small local set from the actual shelf, camera, lighting, distance, and packaging. Public data cannot replace this acceptance set.

Keep datasets outside Git. Store only manifests and preparation instructions.
