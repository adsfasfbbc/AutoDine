from __future__ import annotations

import random
import threading
import time
from collections import Counter, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from smart_storage_vision.backends import FRUIT_LABELS


COUNT_KEYS = tuple(sorted(FRUIT_LABELS)) + ("good", "defective", "review", "person")
VIDEO_ROLES = {
    "inventory-video": "inventory",
    "security-video": "security",
}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class VideoDashboardState:
    def __init__(
        self,
        *,
        inventory_video: Path,
        security_video: Path,
        loop_enabled: bool,
        mock_unauthorized_enabled: bool,
    ) -> None:
        self.lock = threading.Lock()
        self.loop_enabled = loop_enabled
        self.mock_unauthorized_enabled = mock_unauthorized_enabled
        self.runtime_error: str | None = None
        sources = {
            "inventory-video": inventory_video.name,
            "security-video": security_video.name,
        }
        self.streams = {
            stream_id: {
                "stream_id": stream_id,
                "role": role,
                "source_name": sources[stream_id],
                "status": "waiting",
                "counts": {key: 0 for key in COUNT_KEYS},
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
        self.alerts: deque[dict] = deque(maxlen=50)

    def set_source_fps(self, stream_id: str, source_fps: float) -> None:
        with self.lock:
            self.streams[stream_id]["source_fps"] = round(source_fps, 2)

    def update_stream(
        self,
        stream_id: str,
        counts: Counter[str],
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
            stream["processing_fps"] = round(processing_fps, 1)
            stream["frame_index"] = frame_index
            stream["progress_seconds"] = round(progress_seconds, 2)
            stream["loop_count"] = loop_count
            stream["updated_at"] = utc_timestamp()
            self.frames[stream_id] = frame_jpeg

    def mark_ended(self, stream_id: str) -> None:
        with self.lock:
            self.streams[stream_id]["status"] = "ended"

    def add_mock_unauthorized(self, selected_person: int, person_count: int) -> None:
        with self.lock:
            self.alerts.appendleft(
                {
                    "timestamp": utc_timestamp(),
                    "stream_id": "security-video",
                    "person_index": selected_person,
                    "person_count": person_count,
                    "message": f"[模拟] 人员视频中的人员 #{selected_person} 被随机标记为未授权",
                    "mock": True,
                    "published_to_core": False,
                }
            )

    def set_runtime_error(self, exc: BaseException) -> None:
        with self.lock:
            self.runtime_error = f"{type(exc).__name__}: {exc}"
            for stream in self.streams.values():
                if stream["status"] != "ended":
                    stream["status"] = "error"

    def snapshot(self) -> dict:
        with self.lock:
            streams = [{**stream, "counts": dict(stream["counts"])} for stream in self.streams.values()]
            inventory_counts = self.streams["inventory-video"]["counts"]
            security_counts = self.streams["security-video"]["counts"]
            return {
                "mode": "video_file",
                "count_semantics": "role_separated_cumulative_unique_tracks",
                "video_roles": dict(VIDEO_ROLES),
                "loop_enabled": self.loop_enabled,
                "mock_unauthorized_enabled": self.mock_unauthorized_enabled,
                "mock_notice": "模拟预警仅用于界面演示，不生成ADP事件，不发布到Core。",
                "runtime_error": self.runtime_error,
                "inventory_counts": {
                    key: int(inventory_counts[key])
                    for key in tuple(sorted(FRUIT_LABELS)) + ("good", "defective", "review")
                },
                "security_counts": {"person": int(security_counts["person"])},
                "streams": streams,
                "alerts": list(self.alerts),
            }

    def frame(self, stream_id: str) -> bytes | None:
        with self.lock:
            return self.frames.get(stream_id)


class RoleSeparatedVideoRuntime:
    """Run inventory inference on one video and person inference on another."""

    def __init__(
        self,
        *,
        analyzer,
        inventory_video: str | Path,
        security_video: str | Path,
        loop: bool = True,
        playback_rate: float = 1.0,
        mock_unauthorized_rate: float = 0.0,
        mock_check_interval_seconds: float = 8.0,
        random_seed: int | None = None,
    ) -> None:
        inventory_path = Path(inventory_video).resolve()
        security_path = Path(security_video).resolve()
        if inventory_path == security_path:
            raise ValueError("inventory and security videos must be different files")
        if playback_rate <= 0:
            raise ValueError("playback_rate must be greater than zero")
        if not 0.0 <= mock_unauthorized_rate <= 1.0:
            raise ValueError("mock_unauthorized_rate must be between 0 and 1")
        self.analyzer = analyzer
        self.video_sources = {
            "inventory-video": inventory_path,
            "security-video": security_path,
        }
        self.stream_ids = list(VIDEO_ROLES)
        self.loop = loop
        self.playback_rate = playback_rate
        self.mock_unauthorized_rate = mock_unauthorized_rate
        self.mock_check_interval_seconds = mock_check_interval_seconds
        self.random = random.Random(random_seed)
        self.state = VideoDashboardState(
            inventory_video=inventory_path,
            security_video=security_path,
            loop_enabled=loop,
            mock_unauthorized_enabled=mock_unauthorized_rate > 0,
        )
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.captures = []
        self.source_fps: dict[str, float] = {}
        self.error: BaseException | None = None
        self.next_mock_check = 0.0

    def start(self) -> None:
        import cv2

        if self.thread is not None and self.thread.is_alive():
            raise RuntimeError("video dashboard runtime is already running")
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
        self.thread = threading.Thread(target=self._run, name="autodine-video-dashboard", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=20)
            if self.thread.is_alive():
                raise RuntimeError("video dashboard runtime did not stop within 20 seconds")

    def snapshot(self) -> dict:
        return self.state.snapshot()

    def frame(self, stream_id: str) -> bytes | None:
        return self.state.frame(stream_id)

    def _run(self) -> None:
        import cv2

        started = time.perf_counter()
        processed_frames = Counter()
        loop_counts = Counter()
        ended: set[str] = set()
        next_frame_at = {stream_id: time.monotonic() for stream_id in self.stream_ids}
        try:
            while not self.stop_event.is_set() and len(ended) < len(self.stream_ids):
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
                    else:
                        annotated, counts = self.analyzer.analyze_security(
                            frame,
                            accumulate=loop_counts[stream_id] == 0,
                        )
                    encoded_ok, encoded = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if not encoded_ok:
                        raise RuntimeError(f"failed to encode {stream_id} frame as JPEG")
                    processed_frames[stream_id] += 1
                    elapsed = max(time.perf_counter() - started, 0.001)
                    self.state.update_stream(
                        stream_id,
                        counts,
                        processed_frames[stream_id] / elapsed,
                        encoded.tobytes(),
                        int(capture.get(cv2.CAP_PROP_POS_FRAMES)),
                        float(capture.get(cv2.CAP_PROP_POS_MSEC)) / 1000.0,
                        loop_counts[stream_id],
                    )
                    if stream_id == "security-video":
                        self._maybe_add_mock_alert(self.analyzer.current_security_count, time.monotonic())
                    frame_interval = 1.0 / self.source_fps[stream_id] / self.playback_rate
                    next_frame_at[stream_id] = max(next_frame_at[stream_id] + frame_interval, time.monotonic())
                    did_work = True
                if not did_work:
                    self.stop_event.wait(0.005)
        except BaseException as exc:
            self.error = exc
            self.state.set_runtime_error(exc)
            raise
        finally:
            for capture in self.captures:
                capture.release()
            self.captures = []

    def _maybe_add_mock_alert(self, person_count: int, now: float) -> None:
        if self.mock_unauthorized_rate == 0 or person_count == 0:
            return
        if now < self.next_mock_check:
            return
        self.next_mock_check = now + self.mock_check_interval_seconds
        if self.random.random() < self.mock_unauthorized_rate:
            self.state.add_mock_unauthorized(self.random.randint(1, person_count), person_count)


def create_video_dashboard_app(runtime: RoleSeparatedVideoRuntime, html_path: Path):
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import FileResponse, Response

    @asynccontextmanager
    async def lifespan(_app):
        runtime.start()
        try:
            yield
        finally:
            runtime.stop()

    app = FastAPI(title="AutoDine A Offline Video Dashboard", lifespan=lifespan)

    @app.get("/", include_in_schema=False)
    def dashboard_page():
        return FileResponse(html_path, headers={"Cache-Control": "no-store"})

    @app.get("/api/state")
    def dashboard_state():
        return runtime.snapshot()

    @app.get("/api/videos/{stream_id}/frame.jpg", include_in_schema=False)
    def video_frame(stream_id: str):
        if stream_id not in runtime.stream_ids:
            raise HTTPException(status_code=404, detail="unknown video stream")
        frame = runtime.frame(stream_id)
        if frame is None:
            raise HTTPException(status_code=503, detail="video frame is not ready")
        return Response(frame, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    return app
