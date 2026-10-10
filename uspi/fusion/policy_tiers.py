"""Policy tiers, hysteresis and alert budget (C21, architecture sections 7,
11.3, 12.2). Tier 3 uses a short pause with a checklist, never a hard
block (section 11.3).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from uspi.common.config import load_yaml


@dataclass
class TierDecision:
    tier: str  # "tier0_none" | "tier1_info" | "tier2_warn" | "tier3_pause"
    probability: float
    alert_budget_remaining: int
    alert_suppressed_by_budget: bool


@dataclass
class UserAlertBudgetState:
    user_hash: str
    day_bucket: str
    alerts_sent_today: int = 0


class PolicyTierEngine:
    def __init__(self, config_path: str = "tiers.yaml") -> None:
        cfg = load_yaml(config_path)
        self.tier1_threshold = cfg.get("tier1_threshold", 0.3)
        self.tier2_threshold = cfg.get("tier2_threshold", 0.6)
        self.tier3_threshold = cfg.get("tier3_threshold", 0.85)
        self.alert_budget_per_day = cfg.get("alert_budget_per_user_per_day", 5)
        self.config_version = cfg.get("_config_version", "unversioned")
        self._budgets: Dict[str, UserAlertBudgetState] = {}

    def _tier_for_probability(self, p: float) -> str:
        if p >= self.tier3_threshold:
            return "tier3_pause"
        if p >= self.tier2_threshold:
            return "tier2_warn"
        if p >= self.tier1_threshold:
            return "tier1_info"
        return "tier0_none"

    def decide(self, user_hash: str, probability: float, day_bucket: str) -> TierDecision:
        tier = self._tier_for_probability(probability)
        budget_state = self._budgets.setdefault(
            f"{user_hash}:{day_bucket}", UserAlertBudgetState(user_hash=user_hash, day_bucket=day_bucket)
        )
        suppressed = False
        if tier != "tier0_none":
            if budget_state.alerts_sent_today >= self.alert_budget_per_day:
                suppressed = True
                tier = "tier0_none"  # budget respected; still logged, not surfaced
            else:
                budget_state.alerts_sent_today += 1

        remaining = max(0, self.alert_budget_per_day - budget_state.alerts_sent_today)
        return TierDecision(
            tier=tier, probability=probability, alert_budget_remaining=remaining,
            alert_suppressed_by_budget=suppressed,
        )
