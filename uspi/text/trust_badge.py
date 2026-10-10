"""Trust Badge (architecture section 4.3): user-granted, on-device,
expires in 90 days, reduces monitoring but never to zero; hard tripwires
suspend it before the policy runs.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from uspi.common.config import load_yaml

TRIPWIRE_PHRASES = [
    "whitelist me",
    "trust me now",
    "don't flag this",
    "ignore previous warnings",
]


@dataclass
class TrustBadgeState:
    chat_id: str
    granted_ts: Optional[float] = None
    suspended: bool = False
    suspend_reason: Optional[str] = None


class TrustBadgeManager:
    def __init__(self, config_path: str = "trust_badge.yaml") -> None:
        cfg = load_yaml(config_path)
        self.expiry_days = cfg.get("expiry_days", 90)
        self.min_reduction_floor = cfg.get("min_monitoring_floor", 0.2)
        self.config_version = cfg.get("_config_version", "unversioned")
        self._states: Dict[str, TrustBadgeState] = {}

    def grant(self, chat_id: str, now: Optional[float] = None) -> None:
        now = now if now is not None else time.time()
        self._states[chat_id] = TrustBadgeState(chat_id=chat_id, granted_ts=now)

    def revoke(self, chat_id: str) -> None:
        self._states.pop(chat_id, None)

    def check_tripwires(
        self, chat_id: str, text: str, event_flags: List[str]
    ) -> Optional[str]:
        """Returns the tripwire reason if one fires, else None. Tripwires:
        money ask, link to new domain, off-platform request, 'whitelist me'
        phrases, profile/device change."""
        lower = (text or "").lower()
        for phrase in TRIPWIRE_PHRASES:
            if phrase in lower:
                return f"phrase_tripwire:{phrase}"
        for flag in event_flags:
            if flag in {"money_ask", "new_domain_link", "off_platform_request", "profile_change", "device_change"}:
                return f"event_tripwire:{flag}"
        return None

    def status(self, chat_id: str, now: Optional[float] = None) -> TrustBadgeState:
        now = now if now is not None else time.time()
        state = self._states.get(chat_id)
        if state is None:
            return TrustBadgeState(chat_id=chat_id)
        if state.granted_ts and (now - state.granted_ts) > self.expiry_days * 86400:
            self._states.pop(chat_id, None)
            return TrustBadgeState(chat_id=chat_id)
        return state

    def apply_tripwire(self, chat_id: str, text: str, event_flags: List[str]) -> Optional[str]:
        state = self._states.get(chat_id)
        if state is None or state.suspended:
            return None
        reason = self.check_tripwires(chat_id, text, event_flags)
        if reason:
            state.suspended = True
            state.suspend_reason = reason
        return reason

    def monitoring_reduction_factor(self, chat_id: str, now: Optional[float] = None) -> float:
        """Returns a factor in [min_monitoring_floor, 1.0]; never 0 (never
        fully disables monitoring) and 1.0 if no active, unsuspended badge."""
        state = self.status(chat_id, now)
        if state.granted_ts is None or state.suspended:
            return 1.0
        return self.min_reduction_floor
