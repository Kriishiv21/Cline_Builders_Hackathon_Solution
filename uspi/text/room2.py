"""Room 2: per-chat context memory (architecture section 4.3).

Ring buffer, scam-funnel stage tracking, leaky accumulator
s_t = min(S_max, lambda * s_(t-1) + sum new weighted signals), funnel-order
bonus, dormancy-then-burst multiplier.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Deque, Dict, List, Optional

from uspi.common.config import load_yaml


class FunnelStage(IntEnum):
    CONTACT = 0
    RAPPORT = 1
    OFF_PLATFORM = 2
    LINK_OR_PAYMENT = 3
    PRESSURE = 4


_STAGE_CATEGORY_MAP = {
    FunnelStage.CONTACT: set(),
    FunnelStage.RAPPORT: set(),
    FunnelStage.OFF_PLATFORM: {"off_platform"},
    FunnelStage.LINK_OR_PAYMENT: {"money", "otp"},
    FunnelStage.PRESSURE: {"urgency", "authority"},
}


@dataclass
class RoomTwoState:
    chat_id: str
    ring_buffer: Deque[dict] = field(default_factory=lambda: deque(maxlen=200))
    funnel_stage: FunnelStage = FunnelStage.CONTACT
    accumulator: float = 0.0
    last_activity_ts: Optional[float] = None
    counted_categories_this_episode: set = field(default_factory=set)
    activity_history: Deque[float] = field(default_factory=lambda: deque(maxlen=50))


class Room2ChatContext:
    def __init__(self, config_path: str = "room2.yaml") -> None:
        cfg = load_yaml(config_path)
        self.lam = cfg.get("lambda_decay", 0.85)
        self.s_max = cfg.get("s_max", 10.0)
        self.funnel_order_bonus = cfg.get("funnel_order_bonus", 0.3)
        self.dormancy_hours = cfg.get("dormancy_hours", 48.0)
        self.burst_multiplier = cfg.get("burst_multiplier", 1.5)
        self.config_version = cfg.get("_config_version", "unversioned")
        self._states: Dict[str, RoomTwoState] = {}

    def _state(self, chat_id: str) -> RoomTwoState:
        if chat_id not in self._states:
            self._states[chat_id] = RoomTwoState(chat_id=chat_id)
        return self._states[chat_id]

    def ingest_message(
        self, chat_id: str, category_weights: Dict[str, float], ts_utc: float
    ) -> RoomTwoState:
        state = self._state(chat_id)
        state.ring_buffer.append({"ts_utc": ts_utc, "weights": category_weights})

        dormancy_burst = 1.0
        if state.last_activity_ts is not None:
            gap_hours = (ts_utc - state.last_activity_ts) / 3600.0
            if gap_hours >= self.dormancy_hours:
                dormancy_burst = self.burst_multiplier
        state.last_activity_ts = ts_utc
        state.activity_history.append(ts_utc)

        new_signal = 0.0
        for category, weight in category_weights.items():
            if category in state.counted_categories_this_episode:
                continue  # each signal type counted once per episode
            if weight <= 0:
                continue
            state.counted_categories_this_episode.add(category)
            bonus = 0.0
            expected_categories = _STAGE_CATEGORY_MAP.get(state.funnel_stage, set())
            if category in expected_categories:
                bonus = self.funnel_order_bonus
            new_signal += weight * (1.0 + bonus)

        state.accumulator = min(
            self.s_max, self.lam * state.accumulator + new_signal * dormancy_burst
        )
        state.funnel_stage = self._advance_funnel(state, category_weights)
        return state

    def _advance_funnel(
        self, state: RoomTwoState, category_weights: Dict[str, float]
    ) -> FunnelStage:
        stage = state.funnel_stage
        if stage == FunnelStage.CONTACT and len(state.ring_buffer) > 1:
            stage = FunnelStage.RAPPORT
        if category_weights.get("off_platform", 0) > 0 and stage < FunnelStage.OFF_PLATFORM:
            stage = FunnelStage.OFF_PLATFORM
        if (category_weights.get("money", 0) > 0 or category_weights.get("otp", 0) > 0) and stage < FunnelStage.LINK_OR_PAYMENT:
            stage = FunnelStage.LINK_OR_PAYMENT
        if (category_weights.get("urgency", 0) > 0 or category_weights.get("authority", 0) > 0) and stage < FunnelStage.PRESSURE:
            stage = FunnelStage.PRESSURE
        return stage

    def get_state(self, chat_id: str) -> RoomTwoState:
        return self._state(chat_id)
