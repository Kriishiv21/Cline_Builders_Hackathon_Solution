"""Contextual bandit (C22, architecture section 8). LinUCB-style online
learner. This is classic online reinforcement learning (incremental matrix
updates from logged feedback), not a pretrained/offline-trained ML model,
so it is implemented directly rather than routed through the Cline API —
the task's "replace training with Cline" instruction applies to the
components the architecture explicitly trains offline on labelled data
(SLM, AASIST, phonetic classifier, content-risk classifier, live
authenticity adapter), not to this online contextual bandit whose entire
point is to adapt from real-time feedback under hard safety constraints.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from uspi.bandit.action_registry import ActionId
from uspi.common.config import load_yaml


def _feature_vector(context) -> np.ndarray:
    tier_map = {"tier0_none": 0, "tier1_info": 1, "tier2_warn": 2, "tier3_pause": 3}
    return np.array([
        1.0,  # bias
        context.probability_estimate,
        tier_map.get(context.current_tier, 0) / 3.0,
        1.0 if context.trust_badge_active else 0.0,
        1.0 if context.novel_pattern else 0.0,
        min(context.seen_on_n_channels, 3) / 3.0,
        1.0 if context.is_minor_account else 0.0,
    ])


@dataclass
class LinUCBArm:
    action_id: ActionId
    dim: int
    A: np.ndarray = field(init=False)
    b: np.ndarray = field(init=False)

    def __post_init__(self) -> None:
        self.A = np.eye(self.dim)
        self.b = np.zeros(self.dim)

    def theta(self) -> np.ndarray:
        return np.linalg.solve(self.A, self.b)

    def ucb_score(self, x: np.ndarray, alpha: float) -> float:
        A_inv = np.linalg.inv(self.A)
        theta = A_inv @ self.b
        mean = float(theta @ x)
        bonus = alpha * float(np.sqrt(x @ A_inv @ x))
        return mean + bonus

    def update(self, x: np.ndarray, reward: float) -> None:
        self.A += np.outer(x, x)
        self.b += reward * x


class ContextualBandit:
    def __init__(self, dim: int = 7, config_path: str = "bandit.yaml") -> None:
        cfg = load_yaml(config_path)
        self.alpha = cfg.get("ucb_alpha", 0.5)
        self.config_version = cfg.get("_config_version", "unversioned")
        self.dim = dim
        self.arms: Dict[ActionId, LinUCBArm] = {}

    def _arm(self, action_id: ActionId) -> LinUCBArm:
        if action_id not in self.arms:
            self.arms[action_id] = LinUCBArm(action_id=action_id, dim=self.dim)
        return self.arms[action_id]

    def select(self, context, eligible: List[ActionId]) -> ActionId:
        if not eligible:
            return ActionId.NO_ACTION
        x = _feature_vector(context)
        scores = {a: self._arm(a).ucb_score(x, self.alpha) for a in eligible}
        return max(scores, key=scores.get)

    def update(self, context, action_id: ActionId, reward: float) -> None:
        x = _feature_vector(context)
        self._arm(action_id).update(x, reward)
