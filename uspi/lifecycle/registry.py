"""Lifecycle: model/config registry, shadow mode, staged rollout, rollback
(architecture section 12.1).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class RolloutStage(str, Enum):
    SHADOW = "shadow"
    STAGE_1PCT = "1pct"
    STAGE_10PCT = "10pct"
    STAGE_100PCT = "100pct"
    ROLLED_BACK = "rolled_back"


@dataclass
class BundleVersion:
    version: str
    weights_version: str
    lexicon_version: str
    thresholds_version: str
    policy_version: str
    bandit_policy_version: str


class LifecycleManager:
    def __init__(self) -> None:
        self.active_bundle: Optional[BundleVersion] = None
        self.stage: RolloutStage = RolloutStage.SHADOW
        self._halt_reason: Optional[str] = None

    def deploy_shadow(self, bundle: BundleVersion) -> None:
        self.active_bundle = bundle
        self.stage = RolloutStage.SHADOW
        self._halt_reason = None

    def advance_stage(self) -> RolloutStage:
        order = [RolloutStage.SHADOW, RolloutStage.STAGE_1PCT, RolloutStage.STAGE_10PCT, RolloutStage.STAGE_100PCT]
        idx = order.index(self.stage) if self.stage in order else 0
        if idx < len(order) - 1:
            self.stage = order[idx + 1]
        return self.stage

    def halt(self, reason: str) -> None:
        """Automatic halt on drift (PSI), false-positive spikes, latency
        or battery regressions."""
        self._halt_reason = reason

    def rollback(self) -> None:
        """One-switch rollback, drilled (architecture section 12.1)."""
        self.stage = RolloutStage.ROLLED_BACK
