"""Sliding-window aggregation of emotion samples for customer.experience_summary.

Samples (positive / neutral / negative) are collected over a 60-second window
and aggregated into ratio-based summaries, published every 30 seconds.
Windows with zero samples are skipped by the service loop.
"""
from __future__ import annotations

import time
from collections import deque
from typing import Deque, Dict, Optional, Tuple

VALID_SENTIMENTS = ("positive", "neutral", "negative")


class EmotionAggregator:
    """Aggregates per-face sentiment samples over a sliding time window."""

    def __init__(self, window_seconds: float = 60.0) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._window = window_seconds
        self._samples: Deque[Tuple[float, str]] = deque()

    def add(self, sentiment: str, now: Optional[float] = None) -> None:
        if sentiment not in VALID_SENTIMENTS:
            raise ValueError(f"invalid sentiment {sentiment!r}")
        now = time.monotonic() if now is None else now
        self._samples.append((now, sentiment))
        self._evict(now)

    def _evict(self, now: float) -> None:
        cutoff = now - self._window
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()

    def summarize(self, now: Optional[float] = None) -> Dict[str, float]:
        """Return the aggregated summary for the current window.

        Keys: sample_count, positive_ratio, neutral_ratio, negative_ratio.
        When sample_count is 0 all ratios are 0.0; callers skip publishing.
        """
        now = time.monotonic() if now is None else now
        self._evict(now)
        counts = {"positive": 0, "neutral": 0, "negative": 0}
        for _, sentiment in self._samples:
            counts[sentiment] += 1
        total = sum(counts.values())
        if total == 0:
            return {
                "sample_count": 0,
                "positive_ratio": 0.0,
                "neutral_ratio": 0.0,
                "negative_ratio": 0.0,
            }
        return {
            "sample_count": total,
            "positive_ratio": round(counts["positive"] / total, 4),
            "neutral_ratio": round(counts["neutral"] / total, 4),
            "negative_ratio": round(counts["negative"] / total, 4),
        }

    def reset(self) -> None:
        self._samples.clear()
