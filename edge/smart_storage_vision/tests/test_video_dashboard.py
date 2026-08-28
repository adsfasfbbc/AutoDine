from __future__ import annotations

import time
from collections import Counter

import cv2
import numpy as np
from fastapi.testclient import TestClient

from video_stream.inference import CumulativeTrackCounter, Observation
from video_stream.runtime import RoleSeparatedVideoRuntime, VideoDashboardState, create_video_dashboard_app


def test_video_state_keeps_role_results_and_file_metadata_separate(tmp_path) -> None:
    state = VideoDashboardState(
        inventory_video=tmp_path / "fruit.mp4",
        security_video=tmp_path / "people.mp4",
        loop_enabled=True,
        mock_unauthorized_enabled=False,
    )
    state.set_source_fps("inventory-video", 25.0)
    state.update_stream("inventory-video", Counter(apple=2, good=1, review=1), 8.5, b"fruit", 10, 0.4, 0)
    state.update_stream("security-video", Counter(person=3), 12.0, b"people", 12, 0.5, 0)

    snapshot = state.snapshot()

    assert snapshot["mode"] == "video_file"
    assert snapshot["count_semantics"] == "role_separated_cumulative_unique_tracks"
    assert snapshot["inventory_counts"]["apple"] == 2
    assert snapshot["security_counts"] == {"person": 3}
    assert snapshot["streams"][0]["source_name"] == "fruit.mp4"
    assert snapshot["streams"][0]["source_fps"] == 25.0
    assert state.frame("security-video") == b"people"


class FakeAnalyzer:
    current_security_count = 1

    def analyze_inventory(self, frame, *, accumulate=True):
        return frame, Counter(apple=1, good=1)

    def analyze_security(self, frame, *, accumulate=True):
        return frame, Counter(person=1)


def test_cumulative_counter_does_not_sum_the_same_object_each_frame() -> None:
    counter = CumulativeTrackCounter(iou_threshold=0.3, max_missed_frames=2)
    first = Observation("apple", (10, 10, 50, 50), 0.9, "good")
    moved = Observation("apple", (12, 11, 52, 51), 0.88, "good")

    first_ids, first_counts = counter.update([first])
    second_ids, second_counts = counter.update([moved])

    assert first_ids == second_ids
    assert first_counts["apple"] == 1
    assert second_counts["apple"] == 1
    assert second_counts["good"] == 1


def test_cumulative_counter_adds_new_tracks_and_freezes_replay() -> None:
    counter = CumulativeTrackCounter(iou_threshold=0.3, max_missed_frames=2)
    counter.update([Observation("person", (0, 0, 30, 60), 0.9)])
    _ids, counts = counter.update(
        [
            Observation("person", (1, 0, 31, 60), 0.9),
            Observation("person", (80, 0, 110, 60), 0.85),
        ]
    )
    assert counts["person"] == 2

    _ids, replay_counts = counter.update(
        [Observation("person", (160, 0, 190, 60), 0.8)],
        accumulate=False,
    )
    assert replay_counts["person"] == 2


def write_test_video(path, color: tuple[int, int, int]) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 20.0, (64, 48))
    assert writer.isOpened()
    for _ in range(3):
        writer.write(np.full((48, 64, 3), color, dtype=np.uint8))
    writer.release()


def test_video_runtime_reaches_clean_ended_state_without_looping(tmp_path) -> None:
    inventory_video = tmp_path / "fruit.avi"
    security_video = tmp_path / "people.avi"
    write_test_video(inventory_video, (0, 0, 255))
    write_test_video(security_video, (255, 0, 0))
    runtime = RoleSeparatedVideoRuntime(
        analyzer=FakeAnalyzer(),
        inventory_video=inventory_video,
        security_video=security_video,
        loop=False,
        playback_rate=100.0,
    )

    runtime.start()
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        snapshot = runtime.snapshot()
        if all(stream["status"] == "ended" for stream in snapshot["streams"]):
            break
        time.sleep(0.01)
    runtime.stop()

    snapshot = runtime.snapshot()
    assert snapshot["runtime_error"] is None
    assert [stream["status"] for stream in snapshot["streams"]] == ["ended", "ended"]
    assert snapshot["inventory_counts"]["apple"] == 1
    assert snapshot["security_counts"]["person"] == 1
    assert runtime.frame("inventory-video") is not None


def test_video_sources_must_be_different(tmp_path) -> None:
    source = tmp_path / "same.mp4"
    try:
        RoleSeparatedVideoRuntime(analyzer=object(), inventory_video=source, security_video=source)
    except ValueError as exc:
        assert "different" in str(exc)
    else:
        raise AssertionError("duplicate video sources must be rejected")


class FakeRuntime:
    stream_ids = ["inventory-video", "security-video"]

    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def snapshot(self) -> dict:
        return {
            "mode": "video_file",
            "inventory_counts": {"apple": 0},
            "security_counts": {"person": 0},
            "streams": [],
            "alerts": [],
        }

    def frame(self, stream_id: str) -> bytes | None:
        return b"jpeg" if stream_id == "inventory-video" else None


def test_video_dashboard_http_contract(tmp_path) -> None:
    html = tmp_path / "dashboard.html"
    html.write_text("<html>AutoDine video</html>", encoding="utf-8")
    runtime = FakeRuntime()

    with TestClient(create_video_dashboard_app(runtime, html)) as client:
        assert client.get("/").status_code == 200
        assert client.get("/api/state").json()["mode"] == "video_file"
        frame = client.get("/api/videos/inventory-video/frame.jpg")
        assert frame.status_code == 200
        assert frame.headers["content-type"] == "image/jpeg"
        assert client.get("/api/videos/security-video/frame.jpg").status_code == 503
        assert client.get("/api/videos/unknown/frame.jpg").status_code == 404

    assert runtime.started is True
    assert runtime.stopped is True
