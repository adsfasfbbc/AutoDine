from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from smart_storage_vision.backends import FRUIT_LABELS, quality_prediction_for_fruit


@dataclass(frozen=True)
class Observation:
    label: str
    box: tuple[int, int, int, int]
    confidence: float
    quality_status: str | None = None
    quality_confidence: float | None = None
    raw_quality_label: str | None = None


@dataclass
class _Track:
    label: str
    box: tuple[int, int, int, int]
    missed_frames: int = 0
    quality_status: str | None = None


class CumulativeTrackCounter:
    """Greedy IoU tracker used only by the offline video prototype."""

    def __init__(self, *, iou_threshold: float = 0.3, max_missed_frames: int = 15) -> None:
        if not 0.0 < iou_threshold <= 1.0:
            raise ValueError("iou_threshold must be in (0, 1]")
        if max_missed_frames < 0:
            raise ValueError("max_missed_frames must be non-negative")
        self.iou_threshold = iou_threshold
        self.max_missed_frames = max_missed_frames
        self.next_track_id = 1
        self.active_tracks: dict[int, _Track] = {}
        self.counted_tracks: dict[int, _Track] = {}

    def update(self, observations: list[Observation], *, accumulate: bool = True) -> tuple[list[int], Counter[str]]:
        for track in self.active_tracks.values():
            track.missed_frames += 1
        expired = [
            track_id
            for track_id, track in self.active_tracks.items()
            if track.missed_frames > self.max_missed_frames
        ]
        for track_id in expired:
            del self.active_tracks[track_id]

        candidates = []
        for observation_index, observation in enumerate(observations):
            for track_id, track in self.active_tracks.items():
                if observation.label != track.label:
                    continue
                score = self._iou(observation.box, track.box)
                if score >= self.iou_threshold:
                    candidates.append((score, observation_index, track_id))
        candidates.sort(reverse=True)

        assigned_observations: set[int] = set()
        assigned_tracks: set[int] = set()
        assignments: list[int | None] = [None] * len(observations)
        for _score, observation_index, track_id in candidates:
            if observation_index in assigned_observations or track_id in assigned_tracks:
                continue
            observation = observations[observation_index]
            track = self.active_tracks[track_id]
            track.box = observation.box
            track.missed_frames = 0
            track.quality_status = observation.quality_status
            assignments[observation_index] = track_id
            assigned_observations.add(observation_index)
            assigned_tracks.add(track_id)
            if accumulate and track_id in self.counted_tracks:
                self.counted_tracks[track_id].quality_status = observation.quality_status

        for observation_index, observation in enumerate(observations):
            if assignments[observation_index] is not None:
                continue
            track_id = self.next_track_id
            self.next_track_id += 1
            track = _Track(
                label=observation.label,
                box=observation.box,
                quality_status=observation.quality_status,
            )
            self.active_tracks[track_id] = track
            assignments[observation_index] = track_id
            if accumulate:
                self.counted_tracks[track_id] = _Track(
                    label=track.label,
                    box=track.box,
                    quality_status=track.quality_status,
                )

        return [int(track_id) for track_id in assignments], self.counts()

    def counts(self) -> Counter[str]:
        counts: Counter[str] = Counter()
        for track in self.counted_tracks.values():
            counts[track.label] += 1
            if track.quality_status is not None:
                counts[track.quality_status] += 1
        return counts

    @staticmethod
    def _iou(first: tuple[int, int, int, int], second: tuple[int, int, int, int]) -> float:
        x1 = max(first[0], second[0])
        y1 = max(first[1], second[1])
        x2 = min(first[2], second[2])
        y2 = min(first[3], second[3])
        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        first_area = max(0, first[2] - first[0]) * max(0, first[3] - first[1])
        second_area = max(0, second[2] - second[0]) * max(0, second[3] - second[1])
        union = first_area + second_area - intersection
        return intersection / union if union else 0.0


class VideoYoloTrackingAnalyzer:
    """YOLO26 inference plus video-local cumulative track counting."""

    def __init__(
        self,
        *,
        fruit_detector_path: str | Path,
        person_detector_path: str | Path,
        quality_model_path: str | Path,
        detection_confidence: float = 0.25,
        quality_confidence: float = 0.7,
        tracking_iou: float = 0.3,
        tracking_max_missed: int = 15,
    ) -> None:
        import torch
        from ultralytics import YOLO

        self.fruit_detector = YOLO(str(fruit_detector_path))
        self.person_detector = YOLO(str(person_detector_path))
        self.quality_model = YOLO(str(quality_model_path))
        self.detection_confidence = detection_confidence
        self.quality_confidence = quality_confidence
        self.device = 0 if torch.cuda.is_available() else "cpu"
        self.inventory_counter = CumulativeTrackCounter(
            iou_threshold=tracking_iou,
            max_missed_frames=tracking_max_missed,
        )
        self.security_counter = CumulativeTrackCounter(
            iou_threshold=tracking_iou,
            max_missed_frames=tracking_max_missed,
        )
        self.current_security_count = 0

    def analyze_inventory(self, frame, *, accumulate: bool = True):
        import cv2

        source_frame = frame.copy()
        result = self.fruit_detector.predict(
            source=source_frame,
            conf=self.detection_confidence,
            device=self.device,
            verbose=False,
        )[0]
        fruit_items = []
        if result.boxes is not None:
            for box, class_id, detection_confidence in zip(
                result.boxes.xyxy.cpu().tolist(),
                result.boxes.cls.cpu().tolist(),
                result.boxes.conf.cpu().tolist(),
            ):
                label = str(result.names[int(class_id)]).lower()
                if label not in FRUIT_LABELS:
                    continue
                clipped = self._clip_box(box, frame.shape[1], frame.shape[0])
                x1, y1, x2, y2 = clipped
                fruit_items.append((label, float(detection_confidence), clipped, source_frame[y1:y2, x1:x2]))

        quality_results = (
            self.quality_model.predict(
                source=[item[3] for item in fruit_items],
                device=self.device,
                verbose=False,
            )
            if fruit_items
            else []
        )
        observations = []
        for (label, detection_confidence, box, _crop), quality_result in zip(fruit_items, quality_results):
            status, raw_label, quality_confidence = quality_prediction_for_fruit(
                quality_result.probs.data.cpu().tolist(),
                quality_result.names,
                label,
                self.quality_confidence,
            )
            observations.append(
                Observation(
                    label=label,
                    box=box,
                    confidence=detection_confidence,
                    quality_status=status,
                    quality_confidence=quality_confidence,
                    raw_quality_label=raw_label,
                )
            )
        track_ids, cumulative_counts = self.inventory_counter.update(observations, accumulate=accumulate)
        for observation, track_id in zip(observations, track_ids):
            color = {
                "good": (30, 180, 30),
                "defective": (20, 20, 230),
                "review": (0, 190, 255),
            }[observation.quality_status]
            self._draw_observation(
                frame,
                observation,
                color,
                f"{observation.label} ID{track_id} | {observation.quality_status}",
                cv2,
            )
        return frame, cumulative_counts

    def analyze_security(self, frame, *, accumulate: bool = True):
        import cv2

        source_frame = frame.copy()
        result = self.person_detector.predict(
            source=source_frame,
            conf=self.detection_confidence,
            classes=[0],
            device=self.device,
            verbose=False,
        )[0]
        observations = []
        if result.boxes is not None:
            for box, detection_confidence in zip(
                result.boxes.xyxy.cpu().tolist(),
                result.boxes.conf.cpu().tolist(),
            ):
                observations.append(
                    Observation(
                        label="person",
                        box=self._clip_box(box, frame.shape[1], frame.shape[0]),
                        confidence=float(detection_confidence),
                    )
                )
        self.current_security_count = len(observations)
        track_ids, cumulative_counts = self.security_counter.update(observations, accumulate=accumulate)
        for observation, track_id in zip(observations, track_ids):
            self._draw_observation(
                frame,
                observation,
                (255, 160, 0),
                f"person ID{track_id} {observation.confidence:.2f}",
                cv2,
            )
        return frame, cumulative_counts

    @staticmethod
    def _clip_box(box, width: int, height: int) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = (int(value) for value in box)
        return max(0, x1), max(0, y1), min(width, x2), min(height, y2)

    @staticmethod
    def _draw_observation(frame, observation: Observation, color, text: str, cv2) -> None:
        x1, y1, x2, y2 = observation.box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        scale = max(0.5, min(1.2, frame.shape[1] / 960 * 0.7))
        font = cv2.FONT_HERSHEY_SIMPLEX
        thickness = 2 if scale >= 0.8 else 1
        (width, height), baseline = cv2.getTextSize(text, font, scale, thickness)
        top = max(0, y1 - height - baseline - 6)
        cv2.rectangle(frame, (x1, top), (x1 + width + 6, y1), color, -1)
        cv2.putText(frame, text, (x1 + 3, y1 - baseline - 3), font, scale, (255, 255, 255), thickness)
