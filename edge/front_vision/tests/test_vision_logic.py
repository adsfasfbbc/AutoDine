"""Unit tests for emotion mapping, aggregation math and count smoothing.

All tests run without a camera, GPU or any model file.
"""
from __future__ import annotations

import pytest

from front_vision.aggregator import EmotionAggregator
from front_vision.emotion import HSEMOTION_CLASSES, sentiment_for_emotion
from front_vision.people import CountSmoother, box_center_in_roi, count_in_roi


# --- emotion mapping -------------------------------------------------------

def test_all_hsemotion_classes_have_a_mapping() -> None:
    for cls in HSEMOTION_CLASSES:
        assert sentiment_for_emotion(cls) in ("positive", "neutral", "negative")


@pytest.mark.parametrize(
    "emotion,expected",
    [
        ("happiness", "positive"), ("happy", "positive"), ("surprise", "positive"),
        ("anger", "negative"), ("angry", "negative"), ("disgust", "negative"),
        ("fear", "negative"), ("sadness", "negative"), ("sad", "negative"),
        ("neutral", "neutral"), ("contempt", "neutral"),
    ],
)
def test_sentiment_mapping(emotion: str, expected: str) -> None:
    assert sentiment_for_emotion(emotion) == expected


def test_unknown_emotion_defaults_to_neutral() -> None:
    assert sentiment_for_emotion("bored") == "neutral"


# --- aggregator ------------------------------------------------------------

def test_aggregator_ratios_sum_to_one() -> None:
    agg = EmotionAggregator(window_seconds=60.0)
    for s in ["positive", "positive", "negative", "neutral"]:
        agg.add(s, now=100.0)
    summary = agg.summarize(now=100.0)
    assert summary["sample_count"] == 4
    assert summary["positive_ratio"] == 0.5
    assert summary["neutral_ratio"] == 0.25
    assert summary["negative_ratio"] == 0.25
    total = summary["positive_ratio"] + summary["neutral_ratio"] + summary["negative_ratio"]
    assert abs(total - 1.0) < 1e-6


def test_aggregator_empty_window() -> None:
    agg = EmotionAggregator(window_seconds=60.0)
    summary = agg.summarize(now=10.0)
    assert summary["sample_count"] == 0
    assert summary["positive_ratio"] == 0.0


def test_aggregator_evicts_old_samples() -> None:
    agg = EmotionAggregator(window_seconds=60.0)
    agg.add("negative", now=0.0)      # outside the window at t=100
    agg.add("positive", now=95.0)
    agg.add("positive", now=100.0)
    summary = agg.summarize(now=100.0)
    assert summary["sample_count"] == 2
    assert summary["negative_ratio"] == 0.0
    assert summary["positive_ratio"] == 1.0


def test_aggregator_rejects_invalid_sentiment() -> None:
    agg = EmotionAggregator()
    with pytest.raises(ValueError):
        agg.add("ecstatic", now=1.0)


# --- people counting -------------------------------------------------------

def test_smoother_median_of_window() -> None:
    smoother = CountSmoother(window_seconds=3.0)
    smoother.add(0, now=0.0)
    smoother.add(0, now=1.0)
    assert smoother.add(4, now=2.0) == 0  # median of [0, 0, 4]


def test_smoother_evicts_old_samples() -> None:
    smoother = CountSmoother(window_seconds=3.0)
    smoother.add(5, now=0.0)
    assert smoother.add(0, now=10.0) == 0  # old sample expired


def test_roi_full_frame_counts_everything() -> None:
    boxes = [(0, 0, 100, 100), (500, 300, 640, 480)]
    assert count_in_roi(boxes, (0.0, 0.0, 1.0, 1.0), (640, 480)) == 2


def test_roi_left_half_only() -> None:
    left = (0, 0, 100, 100)          # center (50, 50) -> in left half
    right = (500, 0, 600, 100)       # center (550, 50) -> outside
    roi = (0.0, 0.0, 0.5, 1.0)
    assert box_center_in_roi(left, roi, (640, 480)) is True
    assert box_center_in_roi(right, roi, (640, 480)) is False
    assert count_in_roi([left, right], roi, (640, 480)) == 1
