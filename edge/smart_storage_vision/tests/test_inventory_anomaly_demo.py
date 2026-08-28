from __future__ import annotations

from collections import Counter
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from video_inventory_anomaly_demo.inventory import (
    DemoInventoryProvider,
    InventoryAnomalyDetector,
    InventoryItem,
)
from video_inventory_anomaly_demo.runtime import (
    InventoryAnomalyDashboardState,
    InventoryAnomalyVideoRuntime,
    create_dashboard_app,
)
from video_inventory_anomaly_demo.vision import RoleConfidenceAnalyzer


DEMO_ROOT = Path(__file__).resolve().parents[1] / "video_inventory_anomaly_demo"
FIXTURE = DEMO_ROOT / "fixtures" / "inventory_demo_v1.json"


def item(quantity: str, *, policy: str = "TRACKED") -> InventoryItem:
    return InventoryItem(
        ingredient_id="I014",
        name="香蕉",
        base_unit="g",
        inventory_policy=policy,
        physical_quantity=Decimal(quantity),
    )


def test_word_v1_fixture_has_exact_ids_and_unlimited_rules() -> None:
    provider = DemoInventoryProvider(FIXTURE)

    assert len(provider.snapshot()) == 67
    assert set(provider.items) == {f"I{index:03d}" for index in range(1, 68)}
    assert provider.items["I004"].inventory_policy == "UNLIMITED"
    assert provider.items["I005"].inventory_policy == "UNLIMITED"
    assert provider.items["I014"].name == "香蕉"
    assert provider.items["I014"].base_unit == "g"


def test_demo_provider_only_changes_scheduled_banana_inventory() -> None:
    provider = DemoInventoryProvider(FIXTURE)
    before = {entry.ingredient_id: entry.physical_quantity for entry in provider.snapshot()}

    assert provider.advance(3.9) == []
    applied = provider.advance(10.0)
    after = {entry.ingredient_id: entry.physical_quantity for entry in provider.snapshot()}

    assert [timestamp for timestamp, _item in applied] == [4.0, 6.0, 8.0, 10.0]
    assert [changed.physical_quantity for _timestamp, changed in applied] == [
        Decimal("1800"),
        Decimal("1550"),
        Decimal("1250"),
        Decimal("900"),
    ]
    assert after["I014"] == Decimal("900")
    assert {key for key in before if before[key] != after[key]} == {"I014"}


def test_anomaly_requires_sudden_fast_sustained_and_large_reduction() -> None:
    detector = InventoryAnomalyDetector()
    observations = [(0, "2000"), (4, "1800"), (6, "1550"), (8, "1250"), (10, "900")]
    results = [detector.observe(timestamp, item(quantity)) for timestamp, quantity in observations]

    assert results[:-1] == [None, None, None, None]
    anomaly = results[-1]
    assert anomaly is not None
    assert anomaly.ingredient_id == "I014"
    assert anomaly.decrease_quantity == Decimal("1100")
    assert anomaly.consecutive_drops == 4


def test_small_or_unlimited_reduction_does_not_trigger() -> None:
    detector = InventoryAnomalyDetector()
    for timestamp, quantity in [(0, "2000"), (2, "1980"), (4, "1960"), (6, "1940"), (8, "1920")]:
        assert detector.observe(timestamp, item(quantity)) is None
    assert detector.observe(9, item("0", policy="UNLIMITED")) is None


def test_runtime_preserves_each_scheduled_change_when_processing_is_delayed(tmp_path) -> None:
    provider = DemoInventoryProvider(FIXTURE)
    detector = InventoryAnomalyDetector()
    runtime = InventoryAnomalyVideoRuntime(
        analyzer=object(),
        inventory_provider=provider,
        anomaly_detector=detector,
        inventory_video=tmp_path / "fruit.mp4",
        security_video=tmp_path / "people.mp4",
    )
    for inventory_item in provider.snapshot():
        detector.observe(0.0, inventory_item)

    runtime._update_inventory(10.0)

    alerts = runtime.snapshot()["alerts"]
    assert len(alerts) == 1
    assert alerts[0]["category"] == "inventory_reduction"
    assert alerts[0]["decrease_quantity"] == "1100"
    assert alerts[0]["consecutive_drops"] == 4


def test_dashboard_state_separates_model_counts_from_demo_inventory(tmp_path) -> None:
    provider = DemoInventoryProvider(FIXTURE, scenario_enabled=False)
    state = InventoryAnomalyDashboardState(
        inventory_video=tmp_path / "fruit.mp4",
        security_video=tmp_path / "people.mp4",
        inventory_provider=provider,
        loop_enabled=False,
        demo_events_enabled=False,
    )
    state.update_stream(
        "inventory-video",
        Counter(apple=2, good=2),
        current_visible_count=0,
        processing_fps=9.0,
        frame_jpeg=b"fruit",
        frame_index=5,
        progress_seconds=0.2,
        loop_count=0,
    )
    state.update_stream(
        "security-video",
        Counter(person=1),
        current_visible_count=1,
        processing_fps=12.0,
        frame_jpeg=b"person",
        frame_index=5,
        progress_seconds=0.2,
        loop_count=0,
    )

    snapshot = state.snapshot()
    assert snapshot["vision_counts"]["apple"] == 2
    assert snapshot["vision_counts"]["good"] == 2
    assert "milk" not in snapshot["vision_counts"]
    assert snapshot["security_counts"] == {"person": 1, "current_visible": 1}
    assert len(snapshot["inventory"]["items"]) == 67
    assert all(entry["simulated"] is True for entry in snapshot["inventory"]["items"])


class FakeRuntime:
    stream_ids = ["inventory-video", "security-video"]

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def snapshot(self) -> dict:
        return {"inventory": {"items": []}, "alerts": [], "streams": []}

    def frame(self, stream_id: str) -> bytes | None:
        return b"jpeg" if stream_id == "inventory-video" else None


def test_http_contract_exposes_read_only_state_inventory_alerts_and_frames(tmp_path) -> None:
    html = tmp_path / "dashboard.html"
    html.write_text("<html>AutoDine</html>", encoding="utf-8")
    with TestClient(create_dashboard_app(FakeRuntime(), html)) as client:
        assert client.get("/").status_code == 200
        assert client.get("/api/state").status_code == 200
        assert client.get("/api/inventory").json() == {"items": []}
        assert client.get("/api/alerts").json() == []
        assert client.get("/api/videos/inventory-video/frame.jpg").status_code == 200
        assert client.get("/api/videos/security-video/frame.jpg").status_code == 503
        assert client.get("/api/videos/unknown/frame.jpg").status_code == 404


def test_dashboard_uses_demo_wording_and_only_six_fruit_metrics() -> None:
    html = (DEMO_ROOT / "web" / "dashboard.html").read_text(encoding="utf-8")
    assert "mock" not in html.lower()
    assert "演示数据" in html
    assert html.count('data-count="apple"') == 1
    assert html.count('data-count="banana"') == 1
    assert html.count('data-count="grape"') == 1
    assert html.count('data-count="orange"') == 1
    assert html.count('data-count="pineapple"') == 1
    assert html.count('data-count="watermelon"') == 1
    assert 'data-count="milk"' not in html


class ThresholdRecorder:
    device = 0
    detection_confidence = 0.0
    current_security_count = 0

    def analyze_inventory(self, frame, *, accumulate=True):
        return self.detection_confidence, Counter()

    def analyze_security(self, frame, *, accumulate=True):
        return self.detection_confidence, Counter()


def test_fruit_and_person_thresholds_are_independent() -> None:
    recorder = ThresholdRecorder()
    analyzer = RoleConfidenceAnalyzer(recorder, fruit_confidence=0.6, person_confidence=0.25)

    fruit_threshold, _counts = analyzer.analyze_inventory(None)
    person_threshold, _counts = analyzer.analyze_security(None)

    assert fruit_threshold == 0.6
    assert person_threshold == 0.25
