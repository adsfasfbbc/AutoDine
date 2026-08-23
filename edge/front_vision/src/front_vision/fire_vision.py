"""YOLO flame detection for the fire dual-confirmation chain.

A single-class flame model (fire.pt, fine-tuned from YOLO26n — see
scripts/train_fire.py) scores each throttled frame: the best box confidence
becomes vision_conf and any box at/above the threshold sets vision_flag.

Inference backend is switchable like people.py: torch/CUDA is preferred and
the ONNX Runtime export of the same weights (fire.onnx) is the fallback.

Privacy: frames are inferred on in memory only and are never stored.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import numpy as np

from .people import Box, _letterbox, _nms

logger = logging.getLogger("front_vision.fire_vision")

INPUT_SIZE = 640


class _TorchBackend:
    """ultralytics YOLO flame model on torch (CUDA when available)."""

    name = "torch"

    def __init__(self, model_path: str) -> None:
        from ultralytics import YOLO  # type: ignore

        import torch

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = YOLO(model_path)
        logger.info("torch fire backend ready (device=%s, model=%s)", self._device, model_path)

    def detect_with_scores(self, frame: np.ndarray, confidence: float) -> List[Tuple[Box, float]]:
        # Single-class model: no class filter, every box is a flame candidate.
        results = self._model.predict(frame, conf=confidence, verbose=False, device=self._device)
        out: List[Tuple[Box, float]] = []
        for r in results:
            if r.boxes is None:
                continue
            xyxy = r.boxes.xyxy.cpu().numpy()
            confs = r.boxes.conf.cpu().numpy()
            for b, c in zip(xyxy, confs):
                out.append(((float(b[0]), float(b[1]), float(b[2]), float(b[3])), float(c)))
        return out


class _OnnxBackend:
    """Fallback: fire.pt exported to ONNX, executed by onnxruntime."""

    name = "onnxruntime"

    def __init__(self, onnx_path: str) -> None:
        import onnxruntime as ort

        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        available = ort.get_available_providers()
        self._session = ort.InferenceSession(
            onnx_path, providers=[p for p in providers if p in available]
        )
        self._input_name = self._session.get_inputs()[0].name
        logger.info("onnxruntime fire backend ready (%s, providers=%s)", onnx_path, self._session.get_providers())

    def detect_with_scores(self, frame: np.ndarray, confidence: float) -> List[Tuple[Box, float]]:
        import cv2

        img, scale, pad_x, pad_y = _letterbox(frame, INPUT_SIZE)
        blob = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))[None, ...]
        output = self._session.run(None, {self._input_name: blob})[0]
        # Ultralytics ONNX export shape: (1, 4 + n_classes, 8400); the flame
        # model has a single class, but max over class columns works for both.
        preds = output[0].T  # (8400, 4 + n_classes)
        scores_all = preds[:, 4:]
        best_scores = scores_all.max(axis=1)
        mask = best_scores >= confidence
        if not np.any(mask):
            return []
        cx, cy, w, h = preds[mask, 0], preds[mask, 1], preds[mask, 2], preds[mask, 3]
        boxes = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=1)
        scores = best_scores[mask]
        keep = _nms(boxes, scores)
        result: List[Tuple[Box, float]] = []
        for i in keep:
            x1 = (boxes[i, 0] - pad_x) / scale
            y1 = (boxes[i, 1] - pad_y) / scale
            x2 = (boxes[i, 2] - pad_x) / scale
            y2 = (boxes[i, 3] - pad_y) / scale
            result.append(((float(x1), float(y1), float(x2), float(y2)), float(scores[i])))
        return result


class FireDetector:
    """Detects flames with a switchable inference backend (torch preferred)."""

    def __init__(
        self,
        model_path: str,
        onnx_model_path: Optional[str] = None,
        backend: str = "auto",
        confidence: float = 0.25,
    ) -> None:
        self.confidence = confidence
        self._backend = self._init_backend(model_path, onnx_model_path, backend)

    @staticmethod
    def _init_backend(model_path: str, onnx_model_path: Optional[str], backend: str):
        errors: List[str] = []
        if backend in ("auto", "torch"):
            try:
                return _TorchBackend(model_path)
            except Exception as exc:  # torch missing/broken, model missing, ...
                errors.append(f"torch backend unavailable: {exc}")
                if backend == "torch":
                    raise
        if onnx_model_path:
            try:
                return _OnnxBackend(onnx_model_path)
            except Exception as exc:
                errors.append(f"onnxruntime backend unavailable: {exc}")
        raise RuntimeError("no usable fire-detection backend: " + "; ".join(errors))

    @property
    def backend_name(self) -> str:
        return self._backend.name

    def detect_with_scores(self, frame: np.ndarray) -> List[Tuple[Box, float]]:
        return self._backend.detect_with_scores(frame, self.confidence)

    def analyze(self, frame: np.ndarray) -> Tuple[float, bool]:
        """Return (vision_conf, vision_flag) for one frame.

        vision_conf is the best flame-box confidence (0.0 when nothing is
        detected); vision_flag is True when any box clears the threshold.
        """
        detections = self.detect_with_scores(frame)
        if not detections:
            return 0.0, False
        vision_conf = max(score for _, score in detections)
        return float(vision_conf), True
