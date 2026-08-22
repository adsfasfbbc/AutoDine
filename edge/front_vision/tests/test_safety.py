"""Tests for the safety chain: pose features, acoustic arousal, fusion.

All tests are synthetic — no camera, microphone, GPU or model files.
"""
from __future__ import annotations

import numpy as np
import pytest

from front_vision.adp import build_envelope, validate_envelope
from front_vision.config import ENVELOPE_SCHEMA_PATH
from front_vision.safety_audio import (
    RING_BUFFER_SECONDS,
    AcousticArousalMonitor,
    AudioFeatureScorer,
    compute_audio_features,
)
from front_vision.safety_fusion import EVENT_TYPE, SafetyFusion
from front_vision.safety_vision import PoseFeatureWindow

SR = 16000


# --- synthetic keypoints ----------------------------------------------------

def _kps(x: float, y: float, torso: float = 100.0, conf: float = 0.9) -> np.ndarray:
    """One person's COCO keypoints standing at horizontal position x."""
    kps = np.zeros((17, 3), dtype=np.float32)
    kps[:, 2] = conf
    kps[5], kps[6] = (x - 30, y, conf), (x + 30, y, conf)          # shoulders
    kps[11], kps[12] = (x - 20, y + torso, conf), (x + 20, y + torso, conf)  # hips
    kps[9], kps[10] = (x - 60, y + torso / 2, conf), (x + 60, y + torso / 2, conf)  # wrists
    kps[15], kps[16] = (x - 20, y + 2 * torso, conf), (x + 20, y + 2 * torso, conf)  # ankles
    return kps


def _feed(window: PoseFeatureWindow, tracks_fn, frames: int = 21, dt: float = 0.1, t0: float = 0.0):
    """Feed `frames` frames spaced dt apart; tracks_fn(i) -> list of (id, kps)."""
    score, flag = 0.0, False
    for i in range(frames):
        score, flag = window.add(tracks_fn(i), now=t0 + i * dt)
    return score, flag


def test_vision_still_people_no_flag() -> None:
    window = PoseFeatureWindow(window_seconds=2.0, score_threshold=0.6, hysteresis_seconds=0.0)
    score, flag = _feed(window, lambda i: [(1, _kps(200, 100)), (2, _kps(500, 100))])
    assert score == pytest.approx(0.0)
    assert flag is False


def test_vision_single_person_waving_no_flag() -> None:
    window = PoseFeatureWindow(window_seconds=2.0, score_threshold=0.6, hysteresis_seconds=0.0)

    def tracks(i):
        kps = _kps(300, 100)
        kps[10, 0] += 60 if i % 2 else -60   # fast wrist wave, 600 px/s
        return [(1, kps)]

    score, flag = _feed(window, tracks)
    assert 0.4 < score < 0.6    # strong limb cue, but no proximity
    assert flag is False


def test_vision_close_struggle_flags() -> None:
    window = PoseFeatureWindow(window_seconds=2.0, score_threshold=0.6, hysteresis_seconds=0.0)

    def tracks(i):
        a, b = _kps(300, 100), _kps(330, 100)   # torso centers 30px apart
        a[10, 0] += 60 if i % 2 else -60
        b[9, 0] += -60 if i % 2 else 60
        return [(1, a), (2, b)]

    score, flag = _feed(window, tracks)
    assert score >= 0.6
    assert flag is True


def test_vision_falling_person_flags() -> None:
    window = PoseFeatureWindow(window_seconds=2.0, score_threshold=0.6, hysteresis_seconds=0.0)
    score, flag = _feed(window, lambda i: [(1, _kps(300, 100 + i * 40))])  # 400 px/s downward
    assert score >= 0.6
    assert flag is True


def test_vision_hysteresis_holds_flag() -> None:
    window = PoseFeatureWindow(window_seconds=2.0, score_threshold=0.6, hysteresis_seconds=2.0)

    def struggle(i):
        a, b = _kps(300, 100), _kps(330, 100)
        a[10, 0] += 60 if i % 2 else -60
        b[9, 0] += -60 if i % 2 else 60
        return [(1, a), (2, b)]

    _, flag = _feed(window, struggle)
    assert flag is True
    # Struggle stops: score drops, but hysteresis keeps the flag briefly.
    _, flag = _feed(window, lambda i: [(1, _kps(200, 100)), (2, _kps(500, 100))],
                    frames=5, t0=2.1)
    assert flag is True
    _, flag = _feed(window, lambda i: [(1, _kps(200, 100)), (2, _kps(500, 100))],
                    frames=5, t0=5.0)
    assert flag is False


# --- synthetic audio ---------------------------------------------------------

def _silence() -> np.ndarray:
    return np.zeros(2 * SR)


def _white_noise() -> np.ndarray:
    return 0.3 * np.random.default_rng(0).standard_normal(2 * SR)


def _shout_like() -> np.ndarray:
    t = np.arange(2 * SR) / SR
    f = 300 + 80 * np.sin(2 * np.pi * 6 * t)
    envelope = 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 2 * t))
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.4 * envelope).astype(np.float64)


def test_audio_silence_no_flag() -> None:
    scorer = AudioFeatureScorer()
    score, flag = scorer.update(compute_audio_features(_silence(), SR))
    assert score == pytest.approx(0.0)
    assert flag is False


def test_audio_white_noise_flags() -> None:
    scorer = AudioFeatureScorer()
    scorer.update(compute_audio_features(_silence(), SR))  # set baseline first
    score, flag = scorer.update(compute_audio_features(_white_noise(), SR))
    assert flag is True
    assert score >= 0.6


def test_audio_shout_like_flags() -> None:
    scorer = AudioFeatureScorer()
    scorer.update(compute_audio_features(_silence(), SR))
    score, flag = scorer.update(compute_audio_features(_shout_like(), SR))
    assert flag is True
    assert score >= 0.6


def test_audio_ring_buffer_is_bounded() -> None:
    """Privacy: raw PCM retention never exceeds RING_BUFFER_SECONDS."""
    monitor = AcousticArousalMonitor(sample_rate=SR)
    block = np.zeros((int(0.4 * SR), 1), dtype=np.float32)
    for _ in range(10):  # 4s of audio pushed into a 2s buffer
        monitor._callback(block, len(block), None, None)
    assert monitor.buffered_seconds <= RING_BUFFER_SECONDS


# --- fusion ------------------------------------------------------------------

class _FakePublisher:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def enqueue(self, **kwargs) -> None:
        self.events.append(kwargs)


def _fusion() -> tuple:
    pub = _FakePublisher()
    fusion = SafetyFusion(pub, store_id="store-main", device_id="front-cam-01", zone_id="front-hall")
    return fusion, pub


def _step(fusion: SafetyFusion, *, v: bool, a: bool, now: float, vs: float = 0.8, as_: float = 0.7):
    return fusion.update(vision_flag=v, vision_score=vs, audio_flag=a, audio_score=as_, now=now)


def test_fusion_single_modality_never_publishes() -> None:
    # Only vision ever fires.
    fusion, pub = _fusion()
    for t in (0.0, 1.0, 2.0):
        assert _step(fusion, v=True, a=False, now=t) is None
    assert pub.events == []
    # Only audio ever fires.
    fusion, pub = _fusion()
    for t in (0.0, 1.0, 2.0):
        assert _step(fusion, v=False, a=True, now=t) is None
    assert pub.events == []


def test_fusion_stale_single_modality_does_not_fuse() -> None:
    # Vision fired 4s ago — outside the ±3s window when audio fires.
    fusion, pub = _fusion()
    assert _step(fusion, v=True, a=False, now=0.0) is None
    assert _step(fusion, v=False, a=True, now=4.0) is None
    assert pub.events == []


def test_fusion_dual_modality_publishes_warning() -> None:
    fusion, pub = _fusion()
    payload = _step(fusion, v=True, a=True, now=0.0)
    assert payload is not None
    assert payload["event_subtype"] == "violent_interaction"
    assert payload["zone_id"] == "front-hall"
    assert payload["vision_score"] == 0.8 and payload["audio_score"] == 0.7
    assert payload["duration_ms"] == 0
    assert len(pub.events) == 1
    event = pub.events[0]
    assert event["event_type"] == EVENT_TYPE == "vision.front.safety"
    assert event["severity"] == "warning"


def test_fusion_offset_within_window_still_fuses() -> None:
    fusion, pub = _fusion()
    assert _step(fusion, v=True, a=False, now=0.0) is None
    payload = _step(fusion, v=False, a=True, now=2.0)   # ±3s window
    assert payload is not None
    assert len(pub.events) == 1


def test_fusion_cooldown_dedupes_repeat_warnings() -> None:
    fusion, pub = _fusion()
    assert _step(fusion, v=True, a=True, now=0.0) is not None
    assert _step(fusion, v=True, a=True, now=5.0) is None   # same episode, <10s
    assert len(pub.events) == 1


def test_fusion_sustained_episode_escalates_to_critical() -> None:
    fusion, pub = _fusion()
    assert _step(fusion, v=True, a=True, now=0.0)["duration_ms"] == 0
    payload = _step(fusion, v=True, a=True, now=11.0)       # >10s sustained
    assert payload is not None
    assert payload["duration_ms"] == 11000
    assert pub.events[-1]["severity"] == "critical"
    assert len(pub.events) == 2
    assert _step(fusion, v=True, a=True, now=12.0) is None  # escalate once


def test_fusion_retrigger_during_cooldown_is_critical() -> None:
    fusion, pub = _fusion()
    _step(fusion, v=True, a=True, now=0.0)
    _step(fusion, v=False, a=False, now=4.0)                # episode ends (stale)
    payload = _step(fusion, v=True, a=True, now=10.0)       # re-trigger inside 30s cooldown
    assert payload is not None
    assert pub.events[-1]["severity"] == "critical"
    assert len(pub.events) == 2


def test_fusion_after_cooldown_publishes_warning_again() -> None:
    fusion, pub = _fusion()
    _step(fusion, v=True, a=True, now=0.0)
    _step(fusion, v=False, a=False, now=4.0)
    payload = _step(fusion, v=True, a=True, now=35.0)       # cooldown expired
    assert payload is not None
    assert pub.events[-1]["severity"] == "warning"
    assert len(pub.events) == 2


def test_safety_envelope_passes_local_schema() -> None:
    fusion, pub = _fusion()
    _step(fusion, v=True, a=True, now=0.0)
    envelope = build_envelope(**pub.events[0])
    validate_envelope(envelope, ENVELOPE_SCHEMA_PATH)
