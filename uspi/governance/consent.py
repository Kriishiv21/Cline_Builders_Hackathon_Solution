"""Governance: consent and retention (architecture section 11.2).

Granular, revocable consent flags and a deletion job stub.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class ConsentState:
    local_scanning: bool = True
    reputation_queries: bool = False
    report_sharing: bool = False
    guardian_alerts: bool = False


class ConsentStore:
    def __init__(self) -> None:
        self._states: Dict[str, ConsentState] = {}

    def get(self, user_hash: str) -> ConsentState:
        return self._states.setdefault(user_hash, ConsentState())

    def set_consent(self, user_hash: str, **flags) -> ConsentState:
        state = self.get(user_hash)
        for k, v in flags.items():
            if hasattr(state, k):
                setattr(state, k, v)
        return state

    def delete_all(self, user_hash: str) -> None:
        """One-action deletion of local state (architecture section 11.2)."""
        self._states.pop(user_hash, None)
