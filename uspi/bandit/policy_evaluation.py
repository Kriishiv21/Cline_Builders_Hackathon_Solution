"""Off-policy evaluation (OPE) for the bandit (architecture sections 8,
12.2: "OPE with overlap checks"). Implements Inverse Propensity Scoring
(IPS) as the baseline estimator, with an overlap-ratio diagnostic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

from uspi.bandit.action_registry import ActionId
from uspi.bandit.feedback_ledger import LedgerEntry


@dataclass
class LoggedDecision:
    context_features: dict
    action_taken: ActionId
    propensity: float  # probability the logging policy assigned to action_taken
    reward: float


@dataclass
class OPEResult:
    estimated_value: float
    overlap_ratio: float
    n_samples: int
    warning: str | None


def ips_estimate(
    decisions: List[LoggedDecision],
    new_policy_action_fn: Callable[[dict], ActionId],
    min_propensity: float = 0.05,
) -> OPEResult:
    if not decisions:
        return OPEResult(0.0, 0.0, 0, "no logged decisions")

    weighted_sum = 0.0
    overlap_count = 0
    for d in decisions:
        new_action = new_policy_action_fn(d.context_features)
        if new_action == d.action_taken:
            propensity = max(d.propensity, 1e-6)
            weighted_sum += d.reward / propensity
            if d.propensity >= min_propensity:
                overlap_count += 1

    n = len(decisions)
    estimate = weighted_sum / n
    overlap_ratio = overlap_count / n

    warning = None
    if overlap_ratio < 0.1:
        warning = (
            "Low overlap between logging and target policy; IPS estimate is "
            "unreliable. Treat as provisional (architecture section 12.2)."
        )

    return OPEResult(estimated_value=estimate, overlap_ratio=overlap_ratio, n_samples=n, warning=warning)
