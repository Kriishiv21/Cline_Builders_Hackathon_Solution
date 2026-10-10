"""Bandit context builder (architecture section 8/9.3): assembles a
BanditContext from fusion-layer outputs and chat/case state.
"""
from __future__ import annotations

from typing import Optional

from uspi.bandit.context_schema import BanditContext


def build_context(
    case_id: str,
    channel: str,
    probability_estimate: float,
    current_tier: str,
    funnel_stage: Optional[str] = None,
    trust_badge_active: bool = False,
    identification_module_type: Optional[str] = None,
    novel_pattern: bool = False,
    seen_on_n_channels: int = 1,
    alert_budget_remaining: int = 5,
    is_minor_account: bool = False,
    consent_local_scanning: bool = True,
) -> BanditContext:
    return BanditContext(
        case_id=case_id,
        channel=channel,
        probability_estimate=probability_estimate,
        current_tier=current_tier,
        funnel_stage=funnel_stage,
        trust_badge_active=trust_badge_active,
        identification_module_type=identification_module_type,
        novel_pattern=novel_pattern,
        seen_on_n_channels=seen_on_n_channels,
        alert_budget_remaining=alert_budget_remaining,
        is_minor_account=is_minor_account,
        consent_local_scanning=consent_local_scanning,
    )
