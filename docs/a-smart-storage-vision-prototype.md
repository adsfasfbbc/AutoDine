# AutoDine A: SmartStorageVision initial technical prototype

## Delivery boundary

This prototype implements module A only. Real YOLO26 image inference demonstrates fruit counting, whole-fruit quality classification, person detection, ADP v1 events, and AutoDineCore acceptance; Mock remains only for deterministic protocol regression. An NVIDIA Orin USB-camera/JupyterLab session has verified live frames, person boxes/labels/current count, CUDA inference, and clean stop. It does not claim that RTSP, real door/authorization sensors, live-camera ADP publishing, or CountGD++ inference has been completed.

## Architecture decision

```text
RTSP / image / Mock scene
          |
          v
frame sampling + storage-zone mapping
          |
          v
YOLO26 detection/count (current) ----> CountGD++ open-world experiment (paused)
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

CountGD++ remains the preferred research experiment because it supports positive/negative text or visual prompts and pseudo-exemplars, which suits changing fruit/food categories. Its PyTorch 2.7.1/cu128 Docker base image is present locally, but Stage 3, dependencies, checkpoint, inference, and A integration are paused. YOLO26 is therefore the real operational prototype for detection/counting, person detection, and whole-fruit quality classification. Faster R-CNN is retained only as an offline accuracy baseline.

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

- Camera: USB capture is working in JupyterLab on Orin; RTSP remains future work. Credentials stay in environment variables or untracked local configuration and never enter Git.
- NVIDIA Orin: PyTorch 2.3.0/CUDA/OpenCV 4.12.0 plus Ultralytics 8.4.123 has verified live person detection. Old Ultralytics 8.3.58 was incompatible with YOLO26 inference. Fruit field accuracy, sustained FPS, thermal behavior, and end-to-end event latency still require measurement.
- Zeuslap: it is treated as an HDMI display, not a vision compute board. The prototype writes a status JSON; DineWeb or HardwareHub renders/controls the final screen. This keeps module ownership clean.

## Next checkpoints

1. Test real apple/banana/orange scenes on the Orin camera and record count/quality errors and FPS.
2. Add multi-frame stability/debounce before publishing camera observations to the existing ADP/Core path.
3. Replace simulated door/authorization flags with HardwareHub/Core inputs and verify a real unauthorized-entry alarm.
4. Add tracking/line crossing only when cumulative flow count is required; current output is visible-object count.
5. Build the final UI in DineWeb from A/Core interfaces rather than storing camera UI ownership in A.
6. Resume CountGD++ from Stage 3 only after explicit user instruction.

## Definition of done for the next milestone

- A real camera and the Mock source use the same pipeline contract.
- Count error and defect precision/recall are reported on a held-out local session.
- Every business event validates against ADP v1 and is accepted by Core idempotently.
- One authorized removal produces no alarm; one unauthorized removal produces an alarm.
- The Zeuslap screen shows current counts, quality warnings, camera health, and last Core acknowledgement without A importing code from modules C, D, or F.

