"""Policy manager (architecture section 8, phases A-H, section 15 phase
11): gates promotion of the bandit over the baseline, drives rollback.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from uspi.common.config import load_yaml


class PolicyMode(str, Enum):
    BASELINE_ONLY = "baseline_only"
    SHADOW = "shadow"       # bandit runs, baseline still decides
    PROMOTED = "promoted"   # bandit decides


@dataclass
class PromotionDecision:
    promote: bool
    reason: str


class PolicyManager:
    def __init__(self, config_path: str = "bandit.yaml") -> None:
        cfg = load_yaml(config_path)
        self.min_offline_improvement = cfg.get("promotion_min_offline_improvement", 0.05)
        self.config_version = cfg.get("_config_version", "unversioned")
        self.mode = PolicyMode.BASELINE_ONLY

    def evaluate_promotion(self, baseline_value: float, bandit_ope_estimate: float, overlap_ratio: float) -> PromotionDecision:
        if overlap_ratio < 0.1:
            return PromotionDecision(False, "insufficient overlap for a reliable OPE estimate")
        improvement = bandit_ope_estimate - baseline_value
        if improvement >= self.min_offline_improvement:
            return PromotionDecision(True, f"offline improvement {improvement:.3f} >= threshold")
        return PromotionDecision(False, f"offline improvement {improvement:.3f} below threshold")

    def promote(self) -> None:
        self.mode = PolicyMode.PROMOTED

    def enter_shadow(self) -> None:
        self.mode = PolicyMode.SHADOW

    def rollback(self) -> None:
        """One-switch rollback (architecture section 12.1), drilled in CI."""
        self.mode = PolicyMode.BASELINE_ONLY
