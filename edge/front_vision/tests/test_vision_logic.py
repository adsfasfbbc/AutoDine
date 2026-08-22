"""Unit tests for people-count smoothing and ROI filtering.

All tests run without a camera, GPU or any model file.
"""
from __future__ import annotations

from front_vision.people import CountSmoother, box_center_in_roi, count_in_roi


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
