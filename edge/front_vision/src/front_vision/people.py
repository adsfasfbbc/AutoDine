"""Person detection and queue-length estimation.

YOLO (ultralytics, person class only) detects people; detections are counted
inside the configured queue ROI and smoothed with a sliding-window median
before being published as queue.updated events.

Inference backend is switchable: torch/CUDA is preferred (Blackwell sm_120
needs a cu128 torch build); when torch is unavailable the ONNX Runtime
backend (same yolo11n weights exported to ONNX) is used as a fallback.
"""
from __future__ import annotations

import logging
import math
import statistics
import time
from collections import deque
from typing import Deque, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("front_vision.people")

PERSON_CLASS_ID = 0  # COCO "person"
INPUT_SIZE = 640

Box = Tuple[float, float, float, float]  # x1, y1, x2, y2


def _letterbox(frame: np.ndarray, size: int = INPUT_SIZE):
    """Resize with padding to a square; returns (image, scale, pad_x, pad_y)."""
    h, w = frame.shape[:2]
    scale = min(size / w, size / h)
    nw, nh = int(round(w * scale)), int(round(h * scale))
    import cv2

    resized = cv2.resize(frame, (nw, nh))
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    pad_x, pad_y = (size - nw) // 2, (size - nh) // 2
    canvas[pad_y:pad_y + nh, pad_x:pad_x + nw] = resized
    return canvas, scale, pad_x, pad_y


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float = 0.45) -> List[int]:
    """Greedy non-maximum suppression over xyxy boxes."""
    if len(boxes) == 0:
        return []
    x1, y1, x2, y2 = boxes.T
    areas = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    order = scores.argsort()[::-1]
    keep: List[int] = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
        order = order[1:][iou <= iou_thresh]
    return keep


class _TorchBackend:
    """ultralytics YOLO on torch (CUDA when available)."""

    name = "torch"

    def __init__(self, model_path: str) -> None:
        from ultralytics import YOLO  # type: ignore

        import torch

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = YOLO(model_path)
        logger.info("torch backend ready (device=%s, model=%s)", self._device, model_path)

    def detect(self, frame: np.ndarray, confidence: float) -> List[Box]:
        return [b for b, _ in self.detect_with_scores(frame, confidence)]

    def detect_with_scores(self, frame: np.ndarray, confidence: float) -> List[Tuple[Box, float]]:
        results = self._model.predict(
            frame, classes=[PERSON_CLASS_ID], conf=confidence, verbose=False, device=self._device
        )
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
    """Fallback: yolo11n exported to ONNX, executed by onnxruntime."""

    name = "onnxruntime"

    def __init__(self, onnx_path: str, confidence: float) -> None:
        import onnxruntime as ort

        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        available = ort.get_available_providers()
        self._session = ort.InferenceSession(
            onnx_path, providers=[p for p in providers if p in available]
        )
        self._input_name = self._session.get_inputs()[0].name
        self._confidence = confidence
        logger.info("onnxruntime backend ready (%s, providers=%s)", onnx_path, self._session.get_providers())

    def detect(self, frame: np.ndarray, confidence: float) -> List[Box]:
        return [b for b, _ in self.detect_with_scores(frame, confidence)]

    def detect_with_scores(self, frame: np.ndarray, confidence: float) -> List[Tuple[Box, float]]:
        import cv2

        img, scale, pad_x, pad_y = _letterbox(frame)
        blob = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))[None, ...]
        output = self._session.run(None, {self._input_name: blob})[0]
        # Ultralytics ONNX export shape: (1, 84, 8400) -> rows are classes+4.
        preds = output[0].T  # (8400, 84)
        person_scores = preds[:, 4 + PERSON_CLASS_ID]
        mask = person_scores >= confidence
        if not np.any(mask):
            return []
        cx, cy, w, h = preds[mask, 0], preds[mask, 1], preds[mask, 2], preds[mask, 3]
        boxes = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=1)
        scores = person_scores[mask]
        keep = _nms(boxes, scores)
        result: List[Tuple[Box, float]] = []
        for i in keep:
            x1 = (boxes[i, 0] - pad_x) / scale
            y1 = (boxes[i, 1] - pad_y) / scale
            x2 = (boxes[i, 2] - pad_x) / scale
            y2 = (boxes[i, 3] - pad_y) / scale
            result.append(((float(x1), float(y1), float(x2), float(y2)), float(scores[i])))
        return result


class PersonDetector:
    """Detects people with a switchable inference backend (torch preferred)."""

    def __init__(
        self,
        model_path: str,
        onnx_model_path: Optional[str] = None,
        backend: str = "auto",
        confidence: float = 0.4,
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
                return _OnnxBackend(onnx_model_path, 0.4)
            except Exception as exc:
                errors.append(f"onnxruntime backend unavailable: {exc}")
        raise RuntimeError("no usable person-detection backend: " + "; ".join(errors))

    @property
    def backend_name(self) -> str:
        return self._backend.name

    def detect(self, frame: np.ndarray) -> List[Box]:
        return self._backend.detect(frame, self.confidence)

    def detect_with_scores(self, frame: np.ndarray) -> List[Tuple[Box, float]]:
        return self._backend.detect_with_scores(frame, self.confidence)


def box_center_in_roi(box: Box, roi: Tuple[float, float, float, float], frame_size: Tuple[int, int]) -> bool:
    """True if the box center lies inside the ROI.

    roi is normalized (x, y, w, h); frame_size is (width, height).
    """
    fw, fh = frame_size
    rx, ry, rw, rh = roi
    cx = (box[0] + box[2]) / 2.0
    cy = (box[1] + box[3]) / 2.0
    return (rx * fw) <= cx <= ((rx + rw) * fw) and (ry * fh) <= cy <= ((ry + rh) * fh)


def count_in_roi(boxes: List[Box], roi: Tuple[float, float, float, float], frame_size: Tuple[int, int]) -> int:
    return sum(1 for b in boxes if box_center_in_roi(b, roi, frame_size))


class CountSmoother:
    """Sliding-window median smoother for per-frame people counts."""

    def __init__(self, window_seconds: float = 3.0) -> None:
        self._window = window_seconds
        self._samples: Deque[Tuple[float, int]] = deque()

    def add(self, count: int, now: Optional[float] = None) -> int:
        """Record a sample and return the smoothed (median, rounded) count."""
        now = time.monotonic() if now is None else now
        self._samples.append((now, int(count)))
        cutoff = now - self._window
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()
        values = [c for _, c in self._samples]
        return int(math.floor(statistics.median(values) + 0.5))

    def reset(self) -> None:
        self._samples.clear()
