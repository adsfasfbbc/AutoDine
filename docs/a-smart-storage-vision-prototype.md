# AutoDine A: SmartStorageVision initial technical prototype

## Delivery boundary

This prototype implements module A only. It demonstrates the required chain from a stable Mock scene through ingredient counting and quality screening to ADP v1 events that AutoDineCore accepts. It does not claim that CountGD++ has already been installed/trained, that a real RTSP camera has been tested, or that Jetson performance has been measured.

## Architecture decision

```text
RTSP / image / Mock scene
          |
          v
frame sampling + storage-zone mapping
          |
          v
CountGD++ open-world detection/count  ---> low-confidence visual exemplars
          |                                      |
          +---- object crops --------------------+
                          |
                          v
             compact YOLO quality screener
                          |
                 uncertain/conflicting only
                          v
                    optional VLM review
                          |
                          v
calibration (object -> g/ml/pcs) + snapshot comparison
          |
          +--> inventory.detected --> AutoDineCore
          +--> quality.abnormal  --> AutoDineCore
          +--> alarm.opened      --> AutoDineCore/event log
          +--> display_status.json (local demo bridge)
```

CountGD++ is preferred for counting because it supports positive/negative text or visual prompts and pseudo-exemplars, which suits changing fruit/food categories. The official implementation currently expects a Linux/CUDA toolchain and a 1.25 GB checkpoint, so it is isolated behind a backend interface. A compact YOLO model remains the practical Jetson deployment fallback and the first defect classifier. Faster R-CNN is retained only as an offline accuracy baseline; it adds deployment cost without solving open-world prompts.

Counting and defect detection are deliberately separated. CountGD++ localizes/counts the requested ingredient. A quality model evaluates each crop. A VLM is used only when the quality confidence falls below the threshold or the prompt-based and trained models disagree. This bounds latency, cost, and network dependence.

## Inventory semantics

Object counts cannot directly become grams or millilitres. Every visual ingredient needs a versioned calibration such as `one lemon = 120 g`; packaged liquids need package-size identification or a weight sensor. The prototype uses explicit calibration and never changes Core-owned reservations.

```text
physical_quantity = object_count * quantity_per_detection
defective_quantity = confirmed_defective_count * quantity_per_detection
available_quantity = Core(physical - defective - reserved)
```

An unexplained decrease alarm is raised only after comparing stable snapshots and finding no authorized production task reference. Production-task retrieval will be wired to the frozen Core API during Day-7 integration.

## Dataset decision

1. **Counting evaluation - OmniCount-191 fruit subset.** The official CountGD++ repository includes a fruit evaluation path for this dataset. The Hugging Face dataset card lists OpenRAIL++ and a 1.48 GB archive. Use it to compare text-only, positive exemplar, and positive+negative prompt settings.
2. **Quality pretraining - FRUIT-16K.** This CC BY 4.0 dataset contains 16,000 fresh/spoiled images across banana, lemon, lulo, mango, orange, strawberry, tamarillo, and tomato. It is suitable for crop classification pretraining but does not by itself prove shelf-scene detection quality.
3. **Acceptance - AutoDine local set.** Capture the actual RTSP camera, shelf, distance, lighting, packaging, occlusion, and spoilage patterns. Split by capture session, not random adjacent frames. This small domain set is mandatory for the final claim.

Sources: [official CountGD++ repository](https://github.com/niki-amini-naieni/CountGDPlusPlus), [CountGD++ paper](https://arxiv.org/abs/2512.23351), [OmniCount-191 dataset](https://huggingface.co/datasets/cvssp/OmniCount-191), [FRUIT-16K dataset](https://data.mendeley.com/datasets/6ps7gtp2wg/1).

## Hardware path

- Camera: begin with USB/video files, then add an OpenCV/GStreamer RTSP source on Jetson. Credentials stay in environment variables and never enter Git.
- Jetson Orin Nano: benchmark resized frame rate, TensorRT/FP16 YOLO, thermal throttling, and end-to-end event latency. Run CountGD++ remotely first if local memory/latency misses the demo target.
- Zeuslap: it is treated as an HDMI display, not a vision compute board. The prototype writes a status JSON; DineWeb or HardwareHub renders/controls the final screen. This keeps module ownership clean.

## Next checkpoints

1. Freeze A payload fields and production-task authorization query with module C.
2. Capture 100-300 representative local frames and define ingredient/calibration labels.
3. Run CountGD++ zero/few-shot baseline on OmniCount fruit and local frames; record MAE, precision/recall, latency, VRAM, and failure cases.
4. Train a compact YOLO quality model on FRUIT-16K crops plus local data; evaluate per fruit and per defect type.
5. Add RTSP sampling/tracking, debounce over multiple frames, MQTT publishing, and device health.
6. Benchmark on Jetson and choose local CountGD++, local YOLO, or hybrid remote counting based on measured demo constraints.

## Definition of done for the next milestone

- A real camera and the Mock source use the same pipeline contract.
- Count error and defect precision/recall are reported on a held-out local session.
- Every business event validates against ADP v1 and is accepted by Core idempotently.
- One authorized removal produces no alarm; one unauthorized removal produces an alarm.
- The Zeuslap screen shows current counts, quality warnings, camera health, and last Core acknowledgement without A importing code from modules C, D, or F.

