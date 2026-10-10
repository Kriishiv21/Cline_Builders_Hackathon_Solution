"""Calibration and score fusion (C12, architecture section 5.7).

Platt/isotonic calibration fitted on validation data per branch, ECE and
Brier score reporting, and S = wA*A + wP*P fusion with non-negative
weights summing to one. All deterministic/statistical — no LLM call.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from uspi.common.config import load_yaml


@dataclass
class CalibrationModel:
    method: str  # "platt" | "isotonic" | "none"
    _platt: Optional[LogisticRegression] = None
    _isotonic: Optional[IsotonicRegression] = None
    is_fit: bool = False

    @classmethod
    def fit_platt(cls, scores: np.ndarray, labels: np.ndarray) -> "CalibrationModel":
        model = LogisticRegression()
        model.fit(scores.reshape(-1, 1), labels)
        return cls(method="platt", _platt=model, is_fit=True)

    @classmethod
    def fit_isotonic(cls, scores: np.ndarray, labels: np.ndarray) -> "CalibrationModel":
        model = IsotonicRegression(out_of_bounds="clip")
        model.fit(scores, labels)
        return cls(method="isotonic", _isotonic=model, is_fit=True)

    @classmethod
    def identity(cls) -> "CalibrationModel":
        return cls(method="none", is_fit=False)

    def apply(self, score: float) -> float:
        if self.method == "platt" and self._platt is not None:
            return float(self._platt.predict_proba([[score]])[0][1])
        if self.method == "isotonic" and self._isotonic is not None:
            return float(self._isotonic.predict([score])[0])
        return score  # not calibrated; caller must label semantics accordingly


def expected_calibration_error(probs: np.ndarray, labels: np.ndarray, n_bins: int = 10) -> float:
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(probs)
    for i in range(n_bins):
        mask = (probs >= bins[i]) & (probs < bins[i + 1] if i < n_bins - 1 else probs <= bins[i + 1])
        if not np.any(mask):
            continue
        acc = float(np.mean(labels[mask]))
        conf = float(np.mean(probs[mask]))
        ece += (np.sum(mask) / n) * abs(acc - conf)
    return ece


def brier_score(probs: np.ndarray, labels: np.ndarray) -> float:
    return float(np.mean((probs - labels) ** 2))


class ScoreFusion:
    """S = wA * A + wP * P, non-negative weights summing to one."""

    def __init__(self, config_path: str = "voice_fusion.yaml") -> None:
        cfg = load_yaml(config_path)
        self.w_aasist = cfg.get("weight_aasist", 0.6)
        self.w_phonetic = cfg.get("weight_phonetic", 0.4)
        total = self.w_aasist + self.w_phonetic
        if total > 0:
            self.w_aasist /= total
            self.w_phonetic /= total
        self.config_version = cfg.get("_config_version", "unversioned")

    def fuse(self, aasist_score: Optional[float], phonetic_score: Optional[float]) -> Tuple[float, str]:
        """Returns (fused_score, provenance). If a branch is missing,
        returns the other branch's validated score and records provenance,
        or 'inconclusive' per architecture section 5.7."""
        if aasist_score is None and phonetic_score is None:
            return 0.5, "inconclusive"
        if aasist_score is None:
            return phonetic_score, "phonetic_only"
        if phonetic_score is None:
            return aasist_score, "aasist_only"
        fused = self.w_aasist * aasist_score + self.w_phonetic * phonetic_score
        return fused, "fused"
