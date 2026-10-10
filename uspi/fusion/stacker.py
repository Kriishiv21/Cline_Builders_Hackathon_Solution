"""Case-level stacker (C21, architecture section 12.2: "stacker vs simple
average"). Only calibrated_probability signals are usable directly
(score semantics registry, section 3.4); others contribute via a
documented, capped adjustment so they still inform the decision without
being falsely treated as probabilities.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from uspi.common.config import load_yaml
from uspi.common.schema import ScoreSemantics, Signal


@dataclass
class StackedResult:
    probability_estimate: float
    contributing_signal_names: List[str]
    masked_signal_names: List[str]
    method: str


class CaseStacker:
    def __init__(self, config_path: str = "fusion.yaml") -> None:
        cfg = load_yaml(config_path)
        self.default_weight = cfg.get("default_signal_weight", 1.0)
        self.signal_weights: Dict[str, float] = cfg.get("signal_weights", {})
        self.non_prob_signal_cap = cfg.get("non_probability_signal_cap", 0.15)
        self.config_version = cfg.get("_config_version", "unversioned")

    def stack(self, signals: List[Signal]) -> StackedResult:
        usable = [s for s in signals if s.is_usable_in_stacker()]
        masked = [s for s in signals if not s.is_usable_in_stacker()]

        if usable:
            total_w = sum(self.signal_weights.get(s.name, self.default_weight) for s in usable)
            prob = sum(
                self.signal_weights.get(s.name, self.default_weight) * s.value for s in usable
            ) / total_w if total_w > 0 else 0.5
            method = "weighted_average_of_calibrated_probabilities"
        else:
            prob = 0.5
            method = "no_calibrated_signals_neutral_prior"

        # Non-probability (model_score / policy_score) signals nudge the
        # estimate by a capped amount, never dominate it, and are recorded
        # as masked for transparency (never silently dropped).
        adjustment = 0.0
        for s in masked:
            if s.score_semantics == ScoreSemantics.UNAVAILABLE:
                continue
            direction = 1.0 if s.value >= 0.5 else -1.0
            adjustment += direction * self.non_prob_signal_cap * abs(s.value - 0.5) * 2
        adjustment = max(-self.non_prob_signal_cap, min(self.non_prob_signal_cap, adjustment))
        prob = max(0.0, min(1.0, prob + adjustment))

        return StackedResult(
            probability_estimate=prob,
            contributing_signal_names=[s.name for s in usable],
            masked_signal_names=[s.name for s in masked],
            method=method,
        )
