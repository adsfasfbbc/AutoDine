from __future__ import annotations

import threading
import time
from collections import Counter
from pathlib import Path

from .backends import quality_status_from_label


FRUIT_LABELS = {"apple", "banana", "orange"}


def quality_status(label: str, confidence: float, threshold: float) -> str:
    if confidence < threshold:
        return "review"
    return quality_status_from_label(label)


class JupyterCameraSession:
    """Run YOLO26 camera inference in a background thread and update Jupyter widgets."""

    def __init__(
        self,
        *,
        detector_path: str | Path,
        quality_model_path: str | Path,
        camera_source: int | str = 0,
        detection_confidence: float = 0.4,
        quality_confidence: float = 0.7,
        display_width: int = 960,
    ) -> None:
        import torch
        from ultralytics import YOLO

        self.detector = YOLO(str(detector_path))
        self.quality_model = YOLO(str(quality_model_path))
        self.camera_source = camera_source
        self.detection_confidence = detection_confidence
        self.quality_confidence = quality_confidence
        self.display_width = display_width
        self.device = 0 if torch.cuda.is_available() else "cpu"
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.capture = None
        self.error: BaseException | None = None

        import ipywidgets as widgets

        self.image_widget = widgets.Image(format="jpeg")
        self.status_widget = widgets.HTML(value="尚未启动")
        self.stop_button = widgets.Button(description="停止摄像头", button_style="danger")
        self.stop_button.on_click(self._on_stop_clicked)

    def show(self) -> None:
        from IPython.display import display
        import ipywidgets as widgets

        display(widgets.VBox([self.image_widget, self.status_widget, self.stop_button]))

    def start(self) -> None:
        import cv2

        if self.thread is not None and self.thread.is_alive():
            raise RuntimeError("camera session is already running")
        self.stop_event.clear()
        self.error = None
        self.capture = cv2.VideoCapture(self.camera_source)
        if not self.capture.isOpened():
            self.capture.release()
            self.capture = None
            raise RuntimeError(f"cannot open camera source: {self.camera_source!r}")
        self.thread = threading.Thread(target=self._run, name="autodine-camera", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=15)
            if self.thread.is_alive():
                raise RuntimeError("camera inference did not stop within 15 seconds")

    def _on_stop_clicked(self, _button) -> None:
        self.status_widget.value = "正在停止……"
        self.stop()

    def _run(self) -> None:
        import cv2

        started = time.perf_counter()
        frames = 0
        try:
            while not self.stop_event.is_set():
                ok, frame = self.capture.read()
                if not ok:
                    raise RuntimeError("camera returned no frame")
                annotated, counts = self._infer_and_annotate(frame)
                frames += 1
                elapsed = time.perf_counter() - started
                fps = frames / elapsed
                ok, encoded = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if not ok:
                    raise RuntimeError("failed to encode camera frame as JPEG")
                self.image_widget.value = encoded.tobytes()
                self.status_widget.value = self._status_html(counts, fps)
        except BaseException as exc:
            self.error = exc
            self.status_widget.value = f"<b style='color:#b00020'>运行失败：</b>{type(exc).__name__}: {exc}"
            raise
        finally:
            if self.capture is not None:
                self.capture.release()
                self.capture = None
            if self.error is None:
                self.status_widget.value = "摄像头已停止"

    def _infer_and_annotate(self, frame):
        import cv2

        result = self.detector.predict(
            source=frame,
            conf=self.detection_confidence,
            device=self.device,
            verbose=False,
        )[0]
        counts: Counter[str] = Counter()
        if result.boxes is not None:
            for box, class_id, detection_confidence in zip(
                result.boxes.xyxy.cpu().tolist(),
                result.boxes.cls.cpu().tolist(),
                result.boxes.conf.cpu().tolist(),
            ):
                label = str(result.names[int(class_id)]).lower()
                if label != "person" and label not in FRUIT_LABELS:
                    continue
                x1, y1, x2, y2 = self._clip_box(box, frame.shape[1], frame.shape[0])
                if label == "person":
                    counts["person"] += 1
                    text = f"person {detection_confidence:.2f}"
                    color = (255, 160, 0)
                else:
                    crop = frame[y1:y2, x1:x2]
                    quality_result = self.quality_model.predict(
                        source=crop,
                        device=self.device,
                        verbose=False,
                    )[0]
                    top1 = int(quality_result.probs.top1)
                    raw_quality_label = str(quality_result.names[top1])
                    quality_confidence = float(quality_result.probs.top1conf.cpu())
                    status = quality_status(
                        raw_quality_label,
                        quality_confidence,
                        self.quality_confidence,
                    )
                    counts[label] += 1
                    counts[status] += 1
                    text = (
                        f"{label} {detection_confidence:.2f} | "
                        f"{status} {quality_confidence:.2f} ({raw_quality_label})"
                    )
                    color = {
                        "good": (30, 180, 30),
                        "defective": (20, 20, 230),
                        "review": (0, 190, 255),
                    }[status]
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                font_scale = max(0.5, min(1.2, frame.shape[1] / 960 * 0.7))
                self._draw_label(frame, text, x1, y1, color, font_scale)

        if frame.shape[1] > self.display_width:
            scale = self.display_width / frame.shape[1]
            frame = cv2.resize(frame, None, fx=scale, fy=scale)
        return frame, counts

    @staticmethod
    def _clip_box(box, width: int, height: int) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = (int(value) for value in box)
        return max(0, x1), max(0, y1), min(width, x2), min(height, y2)

    @staticmethod
    def _draw_label(frame, text: str, x: int, y: int, color, scale: float) -> None:
        import cv2

        font = cv2.FONT_HERSHEY_SIMPLEX
        thickness = 2 if scale >= 0.8 else 1
        (width, height), baseline = cv2.getTextSize(text, font, scale, thickness)
        top = max(0, y - height - baseline - 6)
        cv2.rectangle(frame, (x, top), (x + width + 6, y), color, -1)
        cv2.putText(frame, text, (x + 3, y - baseline - 3), font, scale, (255, 255, 255), thickness)

    def _status_html(self, counts: Counter[str], fps: float) -> str:
        return (
            f"<b>当前视野：</b>person={counts['person']}，apple={counts['apple']}，"
            f"banana={counts['banana']}，orange={counts['orange']}；"
            f"good={counts['good']}，defective={counts['defective']}，review={counts['review']}；"
            f"FPS={fps:.1f}，device={self.device}"
        )
