"""Interval detector (C13, architecture section 5.8).

Documented smoothing, threshold at the validation operating point, merge
adjacent flags under a maximum gap and minimum duration. Deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from uspi.common.config import load_yaml


@dataclass
class WindowScore:
    start_s: float
    end_s: float
    fused_score: float
    provenance: str
    quality_flags: List[str]


@dataclass
class SuspiciousInterval:
    start_s: float
    end_s: float
    peak_score: float
    window_count: int


class IntervalDetector:
    def __init__(self, config_path: str = "voice_fusion.yaml") -> None:
        cfg = load_yaml(config_path)
        self.smoothing_window_n = cfg.get("smoothing_window_n", 3)
        self.threshold = cfg.get("operating_point_threshold", 0.6)
        self.merge_max_gap_s = cfg.get("merge_max_gap_s", 2.0)
        self.merge_min_duration_s = cfg.get("merge_min_duration_s", 1.0)
        self.config_version = cfg.get("_config_version", "unversioned")

    def smooth(self, windows: List[WindowScore]) -> List[float]:
        scores = [w.fused_score for w in windows]
        n = self.smoothing_window_n
        smoothed = []
        for i in range(len(scores)):
            lo = max(0, i - n // 2)
            hi = min(len(scores), i + n // 2 + 1)
            smoothed.append(float(np.median(scores[lo:hi])))
        return smoothed

    def detect(self, windows: List[WindowScore]) -> List[SuspiciousInterval]:
        if not windows:
            return []
        smoothed = self.smooth(windows)
        flagged = [s >= self.threshold for s in smoothed]

        raw_intervals = []
        start_idx = None
        for i, flag in enumerate(flagged):
            if flag and start_idx is None:
                start_idx = i
            elif not flag and start_idx is not None:
                raw_intervals.append((start_idx, i - 1))
                start_idx = None
        if start_idx is not None:
            raw_intervals.append((start_idx, len(flagged) - 1))

        intervals: List[SuspiciousInterval] = []
        for s_idx, e_idx in raw_intervals:
            start_s = windows[s_idx].start_s
            end_s = windows[e_idx].end_s
            peak = max(smoothed[s_idx : e_idx + 1])
            count = e_idx - s_idx + 1
            if intervals and (start_s - intervals[-1].end_s) <= self.merge_max_gap_s:
                prev = intervals[-1]
                intervals[-1] = SuspiciousInterval(
                    start_s=prev.start_s,
                    end_s=end_s,
                    peak_score=max(prev.peak_score, peak),
                    window_count=prev.window_count + count,
                )
            else:
                intervals.append(SuspiciousInterval(start_s, end_s, peak, count))

        return [iv for iv in intervals if (iv.end_s - iv.start_s) >= self.merge_min_duration_s]
