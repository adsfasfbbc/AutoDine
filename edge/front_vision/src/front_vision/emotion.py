"""Face emotion recognition: YuNet face detection + HSEmotion classification.

Faces are detected with cv2.FaceDetectorYN (YuNet), cropped, and classified
with the HSEmotion ONNX model (8 classes). Everything happens in memory —
no frame or face image is ever written to disk.
"""
from __future__ import annotations

import logging
import os
import shutil
from typing import List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("front_vision.emotion")

# HSEmotion class order (enet_b0_8_best_vgaf.pt / enet_b2_8.onnx).
HSEMOTION_CLASSES = [
    "anger", "contempt", "disgust", "fear", "happiness", "neutral", "sadness", "surprise",
]

# Mapping to the three sentiment buckets used in customer.experience_summary.
# The spec uses the simpler names happy/angry/...; map both spellings.
EMOTION_TO_SENTIMENT = {
    "happiness": "positive",
    "happy": "positive",
    "surprise": "positive",
    "anger": "negative",
    "angry": "negative",
    "disgust": "negative",
    "fear": "negative",
    "sadness": "negative",
    "sad": "negative",
    "neutral": "neutral",
    "contempt": "neutral",
}

FaceBox = Tuple[int, int, int, int]  # x, y, w, h


def sentiment_for_emotion(emotion: str) -> str:
    """Map a raw emotion label to positive / neutral / negative."""
    return EMOTION_TO_SENTIMENT.get(emotion.strip().lower(), "neutral")


def _resolve_ascii_model_path(model_path: str) -> str:
    """Return an ASCII-only path to the model file.

    OpenCV 5.0's ONNX importer cannot open non-ASCII paths on Windows (the
    project may live under e.g. a Chinese directory), and its buffer-based
    FaceDetectorYN.create crashes in this build. So when the path contains
    non-ASCII characters, copy the model to an ASCII cache directory once.
    """
    try:
        model_path.encode("ascii")
        return model_path
    except UnicodeEncodeError:
        pass
    rel = os.path.relpath(model_path)
    try:
        rel.encode("ascii")
        if os.path.isfile(rel):
            return rel
    except (UnicodeEncodeError, ValueError):
        pass
    cache_dir = os.path.join(os.environ.get("PROGRAMDATA", "C:/ProgramData"), "autodine_front_vision")
    os.makedirs(cache_dir, exist_ok=True)
    cached = os.path.join(cache_dir, os.path.basename(model_path))
    if not os.path.isfile(cached) or os.path.getsize(cached) != os.path.getsize(model_path):
        shutil.copyfile(model_path, cached)
    logger.info("non-ASCII model path; using ASCII cache copy at %s", cached)
    return cached


class EmotionAnalyzer:
    """YuNet face detection + HSEmotion emotion classification, fully in-memory."""

    def __init__(self, yunet_model_path: str, face_confidence: float = 0.6) -> None:
        if not hasattr(cv2, "FaceDetectorYN"):
            raise RuntimeError("cv2.FaceDetectorYN is not available in this OpenCV build")
        self._conf_threshold = face_confidence
        self._detector = cv2.FaceDetectorYN.create(
            model=_resolve_ascii_model_path(yunet_model_path),
            config="",
            input_size=(320, 320),
            score_threshold=face_confidence,
            nms_threshold=0.3,
            top_k=5000,
        )
        # hsemotion-onnx 0.3.1 references urllib.request without importing it.
        import urllib.request  # noqa: F401

        from hsemotion_onnx.facial_emotions import HSEmotionRecognizer

        self._recognizer = HSEmotionRecognizer(model_name="enet_b2_8")
        logger.info("emotion analyzer ready (yunet=%s)", yunet_model_path)

    def detect_faces(self, frame: np.ndarray) -> List[FaceBox]:
        h, w = frame.shape[:2]
        self._detector.setInputSize((w, h))
        _, faces = self._detector.detect(frame)
        if faces is None:
            return []
        boxes: List[FaceBox] = []
        for face in faces:
            x, y, fw, fh = (int(face[0]), int(face[1]), int(face[2]), int(face[3]))
            x, y = max(0, x), max(0, y)
            fw = min(fw, w - x)
            fh = min(fh, h - y)
            if fw > 10 and fh > 10:
                boxes.append((x, y, fw, fh))
        return boxes

    def classify(self, frame: np.ndarray, box: FaceBox) -> Optional[str]:
        """Return the sentiment bucket (positive/neutral/negative) for one face crop."""
        x, y, w, h = box
        crop = frame[y:y + h, x:x + w]
        if crop.size == 0:
            return None
        try:
            emotion, _scores = self._recognizer.predict_emotions(crop, logits=False)
        except Exception:
            logger.exception("emotion classification failed")
            return None
        return sentiment_for_emotion(str(emotion))

    def analyze(self, frame: np.ndarray) -> List[str]:
        """Detect all faces in the frame and return one sentiment per face."""
        return [s for b in self.detect_faces(frame) if (s := self.classify(frame, b))]
