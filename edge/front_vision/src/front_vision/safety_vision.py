"""Pose-based violent-interaction cues for safety fusion.

YOLO11n-pose (with simple track IDs) feeds skeleton keypoints into a 2s
sliding-window feature extractor: wrist/ankle speeds, minimum torso distance
between persons and torso drop velocity are combined into a vision_score in
[0, 1]; a threshold with hysteresis yields the vision_flag.

Privacy: only skeleton keypoint trajectories are processed. Frames are never
stored and no appearance or face data leaves the pose model.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("front_vision.safety_vision")

# COCO keypoint indices used by YOLO pose models.
WRISTS = (9, 10)
ANKLES = (15, 16)
SHOULDERS = (5, 6)
HIPS = (11, 12)
MIN_KP_CONF = 0.4

# Normalization references (tuned for 640x480); scores are clipped to [0, 1].
LIMB_SPEED_REF_PX_S = 500.0   # fast waving/struggling wrist speed
DROP_SPEED_REF_PX_S = 250.0   # torso-center downward speed of a fall
PROX_TORSO_FACTOR = 1.5       # torso-center distance, in torso lengths, that reads as "apart"

W_LIMB = 0.45
W_PROX = 0.30
W_DROP = 0.65

TrackSample = Tuple[int, np.ndarray]  # (track_id, keypoints (17, 3) x/y/conf)


def _torso_points(kps: np.ndarray):
    """(torso_center, torso_length) or None when torso keypoints are unreliable."""
    idx = list(SHOULDERS) + list(HIPS)
    if np.any(kps[idx, 2] < MIN_KP_CONF):
        return None
    shoulders = (kps[SHOULDERS[0], :2] + kps[SHOULDERS[1], :2]) / 2.0
    hips = (kps[HIPS[0], :2] + kps[HIPS[1], :2]) / 2.0
    center = (shoulders + hips) / 2.0
    length = float(np.linalg.norm(shoulders - hips))
    return center, max(length, 1e-3)


class PoseFeatureWindow:
    """Sliding-window feature extractor over per-track keypoint trajectories.

    Pure numpy/state logic — no model dependency — so tests can feed
    synthetic keypoint sequences directly.
    """

    def __init__(
        self,
        window_seconds: float = 2.0,
        score_threshold: float = 0.6,
        hysteresis_seconds: float = 2.0,
    ) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._window = window_seconds
        self._threshold = score_threshold
        self._hysteresis = hysteresis_seconds
        self._tracks: Dict[int, Deque[Tuple[float, np.ndarray]]] = {}
        self._above_until = 0.0

    def add(self, tracks: List[TrackSample], now: Optional[float] = None) -> Tuple[float, bool]:
        """Record one frame's tracked keypoints; return (vision_score, vision_flag)."""
        now = time.monotonic() if now is None else now
        cutoff = now - self._window
        for track_id, kps in tracks:
            history = self._tracks.setdefault(int(track_id), deque())
            history.append((now, np.asarray(kps, dtype=np.float32)))
        for track_id in list(self._tracks):
            history = self._tracks[track_id]
            while history and history[0][0] < cutoff:
                history.popleft()
            if not history:
                del self._tracks[track_id]

        score = self._score(now, cutoff)
        if score >= self._threshold:
            self._above_until = now + self._hysteresis
        return score, now <= self._above_until

    # -- internals ---------------------------------------------------------
    def _score(self, now: float, cutoff: float) -> float:
        limb_norm = self._limb_speed_norm()
        drop_norm = self._drop_speed_norm()
        prox_norm = self._proximity_norm()
        score = W_LIMB * limb_norm + W_PROX * prox_norm + W_DROP * drop_norm
        return float(min(1.0, score))

    def _limb_speed_norm(self) -> float:
        speeds: List[float] = []
        for history in self._tracks.values():
            samples = list(history)
            for (t0, k0), (t1, k1) in zip(samples, samples[1:]):
                dt = t1 - t0
                if dt <= 0:
                    continue
                for kp in WRISTS + ANKLES:
                    if k0[kp, 2] >= MIN_KP_CONF and k1[kp, 2] >= MIN_KP_CONF:
                        speeds.append(float(np.linalg.norm(k1[kp, :2] - k0[kp, :2])) / dt)
        if not speeds:
            return 0.0
        # 90th percentile: robust to single-frame tracking jitter.
        peak = float(np.percentile(speeds, 90))
        return min(1.0, peak / LIMB_SPEED_REF_PX_S)

    def _drop_speed_norm(self) -> float:
        best = 0.0
        for history in self._tracks.values():
            samples = list(history)
            for (t0, k0), (t1, k1) in zip(samples, samples[1:]):
                dt = t1 - t0
                if dt <= 0:
                    continue
                torso0, torso1 = _torso_points(k0), _torso_points(k1)
                if torso0 is None or torso1 is None:
                    continue
                # Image y grows downward: positive velocity = falling.
                vy = float(torso1[0][1] - torso0[0][1]) / dt
                best = max(best, vy)
        return min(1.0, best / DROP_SPEED_REF_PX_S) if best > 0 else 0.0

    def _proximity_norm(self) -> float:
        """Closeness of the nearest pair, normalized by torso length."""
        best = 0.0
        # Compare tracks at their newest common timestamp.
        newest: Dict[int, Tuple[np.ndarray, float]] = {}
        for track_id, history in self._tracks.items():
            torso = _torso_points(history[-1][1])
            if torso is not None:
                newest[track_id] = (torso[0], torso[1])
        ids = list(newest)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                c0, l0 = newest[ids[i]]
                c1, l1 = newest[ids[j]]
                dist = float(np.linalg.norm(c0 - c1))
                torso = (l0 + l1) / 2.0
                ratio = dist / (PROX_TORSO_FACTOR * torso)
                best = max(best, min(1.0, max(0.0, 1.0 - ratio)))
        return best

    def reset(self) -> None:
        self._tracks.clear()
        self._above_until = 0.0


class PoseSafetyAnalyzer:
    """YOLO11n-pose wrapper: tracks people and feeds PoseFeatureWindow."""

    def __init__(
        self,
        model_path: str,
        confidence: float = 0.3,
        window_seconds: float = 2.0,
        score_threshold: float = 0.6,
        hysteresis_seconds: float = 2.0,
    ) -> None:
        from ultralytics import YOLO  # type: ignore

        import torch

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = YOLO(model_path)
        self._confidence = confidence
        self.window = PoseFeatureWindow(window_seconds, score_threshold, hysteresis_seconds)
        logger.info("pose safety analyzer ready (device=%s, model=%s)", self._device, model_path)

    def analyze(self, frame: np.ndarray, now: Optional[float] = None) -> Tuple[float, bool]:
        results = self._model.track(
            frame, persist=True, classes=[0], conf=self._confidence,
            verbose=False, device=self._device,
        )
        tracks: List[TrackSample] = []
        for r in results:
            if r.boxes is None or r.boxes.id is None or r.keypoints is None:
                continue
            ids = r.boxes.id.cpu().numpy().astype(int)
            kps = r.keypoints.data.cpu().numpy()  # (n, 17, 3)
            for track_id, kp in zip(ids, kps):
                tracks.append((int(track_id), kp))
        return self.window.add(tracks, now=now)
