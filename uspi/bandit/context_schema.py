"""Bandit context schema (architecture section 8/9.3-9.4)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class BanditContext(BaseModel):
    case_id: str
    channel: str
    probability_estimate: float
    current_tier: str
    funnel_stage: Optional[str] = None
    trust_badge_active: bool = False
    identification_module_type: Optional[str] = None  # per architecture 16.2 #5
    novel_pattern: bool = False
    seen_on_n_channels: int = 1
    alert_budget_remaining: int = 5
    is_minor_account: bool = False
    consent_local_scanning: bool = True
