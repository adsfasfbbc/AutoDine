from __future__ import annotations

import random
import threading
import time
from collections import Counter, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from smart_storage_vision.backends import FRUIT_LABELS

from .inventory import DemoInventoryProvider, InventoryAnomalyDetector


COUNT_KEYS = tuple(sorted(FRUIT_LABELS)) + ("good", "defective", "review", "person")
VIDEO_ROLES = {"inventory-video": "inventory", "security-video": "security"}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class InventoryAnomalyDashboardState:
    def __init__(
        self,
        *,
        inventory_video: Path,
        security_video: Path,
        inventory_provider: DemoInventoryProvider,
        loop_enabled: bool,
        demo_events_enabled: bool,
    ) -> None:
        self.lock = threading.Lock()
        self.loop_enabled = loop_enabled
        self.demo_events_enabled = demo_events_enabled
        self.inventory_provider = inventory_provider
        self.runtime_error: str | None = None
        source_names = {
            "inventory-video": inventory_video.name,
            "security-video": security_video.name,
        }
        self.streams = {
            stream_id: {
                "stream_id": stream_id,
                "role": role,
                "source_name": source_names[stream_id],
                "status": "waiting",
                "counts": {key: 0 for key in COUNT_KEYS},
                "current_visible_count": 0,
                "processing_fps": 0.0,
                "source_fps": 0.0,
                "frame_index": 0,
                "progress_seconds": 0.0,
                "loop_count": 0,
                "updated_at": None,
            }
            for stream_id, role in VIDEO_ROLES.items()
        }
        self.frames: dict[str, bytes] = {}
        self.alerts: deque[dict] = deque(maxlen=100)
        self.pending_events: deque[dict] = deque()

    def set_source_fps(self, stream_id: str, source_fps: float) -> None:
        with self.lock:
            self.streams[stream_id]["source_fps"] = round(source_fps, 2)

    def update_stream(
        self,
        stream_id: str,
        counts: Counter[str],
        *,
        current_visible_count: int,
        processing_fps: float,
        frame_jpeg: bytes,
        frame_index: int,
        progress_seconds: float,
        loop_count: int,
    ) -> None:
        with self.lock:
            stream = self.streams[stream_id]
            stream["status"] = "playing"
            stream["counts"] = {key: int(counts[key]) for key in COUNT_KEYS}
            stream["current_visible_count"] = current_visible_count
            stream["processing_fps"] = round(processing_fps, 1)
            stream["frame_index"] = frame_index
            stream["progress_seconds"] = round(progress_seconds, 2)
            stream["loop_count"] = loop_count
            stream["updated_at"] = utc_timestamp()
            self.frames[stream_id] = frame_jpeg

    def mark_ended(self, stream_id: str) -> None:
        with self.lock:
            self.streams[stream_id]["status"] = "ended"

    def add_inventory_anomaly(self, event: dict) -> None:
        alert = {
            **event,
            "category": "inventory_reduction",
            "severity": "critical",
            "message": (
                f"库存异常减少：{event['ingredient_name']}在{event['window_seconds']:.1f}秒内"
                f"减少{event['decrease_quantity']}{event['unit']}"
            ),
        }
        with self.lock:
            self.alerts.appendleft(alert)
            self.pending_events.append(alert)

    def add_unauthorized_demo(self, selected_person: int, person_count: int) -> None:
        alert = {
            "event_type": "vision.storage.security_candidate",
            "timestamp": utc_timestamp(),
            "category": "unauthorized_entry",
            "severity": "critical",
            "stream_id": "security-video",
            "person_index": selected_person,
            "visible_person_count": person_count,
            "message": f"未授权进入预警：人员 #{selected_person}",
            "simulated": True,
            "published_to_core": False,
        }
        with self.lock:
            self.alerts.appendleft(alert)
            self.pending_events.append(alert)

    def set_runtime_error(self, exc: BaseException) -> None:
        with self.lock:
            self.runtime_error = f"{type(exc).__name__}: {exc}"
            for stream in self.streams.values():
                if stream["status"] != "ended":
                    stream["status"] = "error"

    def snapshot(self) -> dict:
        with self.lock:
            streams = [{**stream, "counts": dict(stream["counts"])} for stream in self.streams.values()]
            vision_counts = self.streams["inventory-video"]["counts"]
            security_counts = self.streams["security-video"]["counts"]
            inventory_items = [
                item.as_dict(simulated=True) for item in self.inventory_provider.snapshot()
            ]
            return {
                "mode": "isolated_video_inventory_anomaly_demo",
                "count_semantics": "six_yolo_fruit_classes_and_person_unique_tracks",
                "video_roles": dict(VIDEO_ROLES),
                "loop_enabled": self.loop_enabled,
                "demo_events_enabled": self.demo_events_enabled,
                "runtime_error": self.runtime_error,
                "data_sources": {
                    "fruit_and_quality": "yolo26_real_inference",
                    "person": "yolo26_real_inference",
                    "inventory": "word_v1_demo_fixture",
                    "authorization": "demo_fixture",
                },
                "vision_counts": {
                    key: int(vision_counts[key])
                    for key in tuple(sorted(FRUIT_LABELS)) + ("good", "defective", "review")
                },
                "security_counts": {
                    "person": int(security_counts["person"]),
                    "current_visible": int(self.streams["security-video"]["current_visible_count"]),
                },
                "inventory": {
                    "store_id": self.inventory_provider.store_id,
                    "location_id": self.inventory_provider.location_id,
                    "specification": dict(self.inventory_provider.specification),
                    "items": inventory_items,
                },
                "streams": streams,
                "alerts": list(self.alerts),
            }

    def drain_events(self) -> list[dict]:
        with self.lock:
            events = list(self.pending_events)
            self.pending_events.clear()
            return events

    def frame(self, stream_id: str) -> bytes | None:
        with self.lock:
            return self.frames.get(stream_id)


class InventoryAnomalyVideoRuntime:
    """Keep the two video roles separate and add a replaceable inventory stream."""

    def __init__(
        self,
        *,
        analyzer,
        inventory_provider: DemoInventoryProvider,
        anomaly_detector: InventoryAnomalyDetector,
        inventory_video: str | Path,
        security_video: str | Path,
        loop: bool = False,
        playback_rate: float = 1.0,
        demo_events_enabled: bool = True,
        unauthorized_delay_seconds: float = 3.0,
        random_seed: int = 17,
    ) -> None:
        inventory_path = Path(inventory_video).resolve()
        security_path = Path(security_video).resolve()
        if inventory_path == security_path:
            raise ValueError("inventory and security videos must be different files")
        if playback_rate <= 0:
            raise ValueError("playback_rate must be greater than zero")
        self.analyzer = analyzer
        self.inventory_provider = inventory_provider
        self.anomaly_detector = anomaly_detector
        self.video_sources = {
            "inventory-video": inventory_path,
            "security-video": security_path,
        }
        self.stream_ids = list(VIDEO_ROLES)
        self.loop = loop
        self.playback_rate = playback_rate
        self.demo_events_enabled = demo_events_enabled
        self.unauthorized_delay_seconds = unauthorized_delay_seconds
        self.random = random.Random(random_seed)
        self.state = InventoryAnomalyDashboardState(
            inventory_video=inventory_path,
            security_video=security_path,
            inventory_provider=inventory_provider,
            loop_enabled=loop,
            demo_events_enabled=demo_events_enabled,
        )
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.captures = []
        self.source_fps: dict[str, float] = {}
        self.error: BaseException | None = None
        self.unauthorized_emitted = False

    def start(self) -> None:
        import cv2

        if self.thread is not None and self.thread.is_alive():
            raise RuntimeError("inventory anomaly runtime is already running")
        self.stop_event.clear()
        self.error = None
        self.captures = []
        self.source_fps = {}
        for stream_id, source in self.video_sources.items():
            capture = cv2.VideoCapture(str(source))
            if not capture.isOpened():
                capture.release()
                for opened in self.captures:
                    opened.release()
                self.captures = []
                raise RuntimeError(f"cannot open video file: {source}")
            fps = float(capture.get(cv2.CAP_PROP_FPS))
            if fps <= 0:
                capture.release()
                for opened in self.captures:
                    opened.release()
                self.captures = []
                raise RuntimeError(f"video has no valid FPS metadata: {source}")
            self.captures.append(capture)
            self.source_fps[stream_id] = fps
            self.state.set_source_fps(stream_id, fps)
        for item in self.inventory_provider.snapshot():
            self.anomaly_detector.observe(0.0, item)
        self.thread = threading.Thread(target=self._run, name="autodine-inventory-anomaly-demo", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=20)
            if self.thread.is_alive():
                raise RuntimeError("inventory anomaly runtime did not stop within 20 seconds")

    def snapshot(self) -> dict:
        return self.state.snapshot()

    def drain_events(self) -> list[dict]:
        return self.state.drain_events()

    def frame(self, stream_id: str) -> bytes | None:
        return self.state.frame(stream_id)

    def is_finished(self) -> bool:
        return self.thread is not None and not self.thread.is_alive()

    def _update_inventory(self, elapsed: float) -> None:
        applied_changes = self.inventory_provider.advance(elapsed) if self.demo_events_enabled else []
        for scheduled_time, item in applied_changes:
            anomaly = self.anomaly_detector.observe(scheduled_time, item)
            if anomaly is not None:
                self.state.add_inventory_anomaly(anomaly.as_dict(utc_timestamp()))

    def _run(self) -> None:
        import cv2

        started = time.perf_counter()
        processed_frames = Counter()
        loop_counts = Counter()
        ended: set[str] = set()
        next_frame_at = {stream_id: time.monotonic() for stream_id in self.stream_ids}
        try:
            while not self.stop_event.is_set() and len(ended) < len(self.stream_ids):
                elapsed = time.perf_counter() - started
                self._update_inventory(elapsed)
                did_work = False
                now = time.monotonic()
                for stream_id, capture in zip(self.stream_ids, self.captures):
                    if stream_id in ended or now < next_frame_at[stream_id]:
                        continue
                    ok, frame = capture.read()
                    if not ok and self.loop:
                        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        loop_counts[stream_id] += 1
                        ok, frame = capture.read()
                    if not ok:
                        if self.loop:
                            raise RuntimeError(f"{stream_id} could not restart after reaching the end")
                        ended.add(stream_id)
                        self.state.mark_ended(stream_id)
                        continue
                    if stream_id == "inventory-video":
                        annotated, counts = self.analyzer.analyze_inventory(
                            frame,
                            accumulate=loop_counts[stream_id] == 0,
                        )
                        current_visible_count = 0
                    else:
                        annotated, counts = self.analyzer.analyze_security(
                            frame,
                            accumulate=loop_counts[stream_id] == 0,
                        )
                        current_visible_count = self.analyzer.current_security_count
                    encoded_ok, encoded = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if not encoded_ok:
                        raise RuntimeError(f"failed to encode {stream_id} frame as JPEG")
                    processed_frames[stream_id] += 1
                    runtime_elapsed = max(time.perf_counter() - started, 0.001)
                    self.state.update_stream(
                        stream_id,
                        counts,
                        current_visible_count=current_visible_count,
                        processing_fps=processed_frames[stream_id] / runtime_elapsed,
                        frame_jpeg=encoded.tobytes(),
                        frame_index=int(capture.get(cv2.CAP_PROP_POS_FRAMES)),
                        progress_seconds=float(capture.get(cv2.CAP_PROP_POS_MSEC)) / 1000.0,
                        loop_count=loop_counts[stream_id],
                    )
                    if (
                        stream_id == "security-video"
                        and self.demo_events_enabled
                        and not self.unauthorized_emitted
                        and elapsed >= self.unauthorized_delay_seconds
                        and current_visible_count > 0
                    ):
                        self.state.add_unauthorized_demo(
                            self.random.randint(1, current_visible_count),
                            current_visible_count,
                        )
                        self.unauthorized_emitted = True
                    frame_interval = 1.0 / self.source_fps[stream_id] / self.playback_rate
                    next_frame_at[stream_id] = max(next_frame_at[stream_id] + frame_interval, time.monotonic())
                    did_work = True
                if not did_work:
                    self.stop_event.wait(0.005)
        except BaseException as exc:
            self.error = exc
            self.state.set_runtime_error(exc)
        finally:
            for capture in self.captures:
                capture.release()
            self.captures = []


def create_dashboard_app(runtime: InventoryAnomalyVideoRuntime, html_path: Path):
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse, Response

    @asynccontextmanager
    async def lifespan(_app):
        runtime.start()
        try:
            yield
        finally:
            runtime.stop()

    app = FastAPI(title="AutoDine A Inventory Anomaly Video Demo", lifespan=lifespan)

    @app.get("/", include_in_schema=False)
    def dashboard_page():
        return FileResponse(html_path, headers={"Cache-Control": "no-store"})

    @app.get("/api/state")
    def dashboard_state():
        return runtime.snapshot()

    @app.get("/api/inventory")
    def inventory_state():
        return runtime.snapshot()["inventory"]

    @app.get("/api/alerts")
    def alert_state():
        return runtime.snapshot()["alerts"]

    @app.get("/api/videos/{stream_id}/frame.jpg", include_in_schema=False)
    def video_frame(stream_id: str):
        if stream_id not in runtime.stream_ids:
            raise HTTPException(status_code=404, detail="unknown video stream")
        frame = runtime.frame(stream_id)
        if frame is None:
            raise HTTPException(status_code=503, detail="video frame is not ready")
        return Response(frame, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    return app
