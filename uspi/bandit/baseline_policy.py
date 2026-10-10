"""Baseline (non-learned) policy: deterministic mapping from tier to the
single most conservative eligible action. Used as the comparison arm for
offline evaluation (architecture section 12.2: "baseline vs bandit offline
report").
"""
from __future__ import annotations

from uspi.bandit.action_registry import ActionId
from uspi.bandit.context_schema import BanditContext
from uspi.bandit.safety_constraints import ConstraintContext, constrained_eligible_actions

_TIER_DEFAULT_ACTION = {
    "tier0_none": ActionId.NO_ACTION,
    "tier1_info": ActionId.SHOW_INFO_BANNER,
    "tier2_warn": ActionId.SHOW_WARNING,
    "tier3_pause": ActionId.PAUSE_WITH_CHECKLIST,
}


def baseline_select(context: BanditContext) -> ActionId:
    ctx = ConstraintContext(
        current_tier=context.current_tier,
        alert_budget_remaining=context.alert_budget_remaining,
        trust_badge_active=context.trust_badge_active,
        is_minor_account=context.is_minor_account,
        consent_local_scanning=context.consent_local_scanning,
    )
    allowed = constrained_eligible_actions(ctx)
    preferred = _TIER_DEFAULT_ACTION.get(context.current_tier, ActionId.NO_ACTION)
    return preferred if preferred in allowed else allowed[0]
