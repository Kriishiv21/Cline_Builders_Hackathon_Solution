"""Reward calculator (architecture section 8/12.2). Reward combines
correct-detection credit, burden cost of the action taken, and a false-
positive penalty. Provenance of the outcome (verified vs simulated) is
tracked so training never mixes unverified feedback silently.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from uspi.bandit.action_registry import REGISTRY, ActionId
from uspi.common.config import load_yaml


@dataclass
class OutcomeLabel:
    verified: bool  # True only for independently verified outcomes
    was_scam: Optional[bool]  # None if unknown/unverified
    user_overrode_alert: bool = False


class RewardCalculator:
    def __init__(self, config_path: str = "bandit.yaml") -> None:
        cfg = load_yaml(config_path)
        self.w_detect = cfg.get("reward_weight_correct_detection", 1.0)
        self.w_burden = cfg.get("reward_weight_burden", -0.5)
        self.w_fp = cfg.get("reward_weight_false_positive", -1.0)
        self.config_version = cfg.get("_config_version", "unversioned")

    def compute(self, action_id: ActionId, outcome: OutcomeLabel) -> float:
        burden = REGISTRY[action_id].burden_cost
        reward = self.w_burden * burden

        if not outcome.verified or outcome.was_scam is None:
            # Unverified outcomes contribute burden cost only; never reward
            # or penalize detection accuracy from unverified labels
            # (architecture section 8: "no training on unverified labels").
            return reward

        acted = action_id != ActionId.NO_ACTION
        if outcome.was_scam and acted:
            reward += self.w_detect
        elif outcome.was_scam and not acted:
            reward += self.w_fp  # missed detection
        elif not outcome.was_scam and acted:
            reward += self.w_fp  # false positive alert
        # not outcome.was_scam and not acted: no additional term, correct quiet case

        if outcome.user_overrode_alert:
            reward += self.w_fp * 0.5  # partial penalty, alert fatigue signal

        return reward
