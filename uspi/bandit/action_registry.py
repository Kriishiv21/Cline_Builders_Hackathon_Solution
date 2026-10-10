"""Part 04 bandit: action registry (C22, architecture section 8).

Actions are the adaptive-action layer's permitted outputs; the bandit
chooses among ELIGIBLE actions only, never invents new ones, and safety
constraints (uspi/bandit/safety_constraints.py) filter eligibility before
the bandit ever sees an action.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List


class ActionId(str, Enum):
    NO_ACTION = "no_action"
    SHOW_INFO_BANNER = "show_info_banner"
    SHOW_WARNING = "show_warning"
    SUGGEST_VERIFY_CHANNEL = "suggest_verify_channel"
    PAUSE_WITH_CHECKLIST = "pause_with_checklist"
    OFFER_REPORT_HANDOFF = "offer_report_handoff"
    REQUEST_HUMAN_REVIEW = "request_human_review"


@dataclass
class ActionSpec:
    action_id: ActionId
    min_tier: str  # minimum policy tier required for eligibility
    burden_cost: float  # harm-metric cost used by the reward calculator
    description: str


REGISTRY: Dict[ActionId, ActionSpec] = {
    ActionId.NO_ACTION: ActionSpec(ActionId.NO_ACTION, "tier0_none", 0.0, "Take no user-facing action."),
    ActionId.SHOW_INFO_BANNER: ActionSpec(ActionId.SHOW_INFO_BANNER, "tier1_info", 0.1, "Low-salience info banner."),
    ActionId.SHOW_WARNING: ActionSpec(ActionId.SHOW_WARNING, "tier2_warn", 0.4, "Visible risk-indicator warning."),
    ActionId.SUGGEST_VERIFY_CHANNEL: ActionSpec(ActionId.SUGGEST_VERIFY_CHANNEL, "tier2_warn", 0.3, "Suggest verifying through a trusted channel."),
    ActionId.PAUSE_WITH_CHECKLIST: ActionSpec(ActionId.PAUSE_WITH_CHECKLIST, "tier3_pause", 0.7, "Short pause with a plain-language checklist, never a hard block."),
    ActionId.OFFER_REPORT_HANDOFF: ActionSpec(ActionId.OFFER_REPORT_HANDOFF, "tier2_warn", 0.2, "Offer handoff to a cybercrime reporting channel."),
    ActionId.REQUEST_HUMAN_REVIEW: ActionSpec(ActionId.REQUEST_HUMAN_REVIEW, "tier1_info", 0.1, "Queue for reviewer console."),
}

_TIER_ORDER = ["tier0_none", "tier1_info", "tier2_warn", "tier3_pause"]


def eligible_actions(current_tier: str) -> List[ActionId]:
    tier_rank = _TIER_ORDER.index(current_tier) if current_tier in _TIER_ORDER else 0
    return [
        spec.action_id
        for spec in REGISTRY.values()
        if _TIER_ORDER.index(spec.min_tier) <= tier_rank
    ]
