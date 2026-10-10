"""Safety constraints (architecture section 1.3 principle 10: "Safety
constraints are enforced outside any learned policy. The bandit cannot
override them."). This module is pure deterministic code with no bandit
or model influence whatsoever.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from uspi.bandit.action_registry import ActionId, eligible_actions


@dataclass
class ConstraintContext:
    current_tier: str
    alert_budget_remaining: int
    trust_badge_active: bool
    is_minor_account: bool
    consent_local_scanning: bool


def constrained_eligible_actions(ctx: ConstraintContext) -> List[ActionId]:
    """Returns the action set the bandit is allowed to choose from. Any
    action outside this list is structurally impossible to select, not
    merely discouraged."""
    actions = eligible_actions(ctx.current_tier)

    if not ctx.consent_local_scanning:
        return [ActionId.NO_ACTION]

    if ctx.alert_budget_remaining <= 0:
        actions = [a for a in actions if a == ActionId.NO_ACTION]

    if ctx.is_minor_account:
        # Stricter defaults for minors (architecture section 11.2): never
        # allow suppression below show_warning once tier2+ is reached.
        if ctx.current_tier in {"tier2_warn", "tier3_pause"} and ActionId.NO_ACTION in actions:
            actions = [a for a in actions if a != ActionId.NO_ACTION]

    return actions or [ActionId.NO_ACTION]
