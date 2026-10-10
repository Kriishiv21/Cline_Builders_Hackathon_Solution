"""Caller-reputation hint adapter (C18, architecture section 6/16.2 #7).

Truecaller SDK capability is unconfirmed in the source documents. This
adapter exposes one interface with two implementations: a real client
(stub, disabled by default) and a mock, so the demo can disclose which is
active (architecture rule: "mock behind the same interface and disclose").
`spam_hint` is a PRIOR only (score semantics registry, section 3.4):
it can scale thresholds but never blocks or suppresses analysis.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from uspi.common.config import env, env_bool


@dataclass
class CallerHint:
    source: str  # "truecaller" | "mock" | "unavailable"
    spam_hint_0_1: Optional[float]
    label: Optional[str]
    is_mock: bool


class CallerHintAdapter(Protocol):
    def lookup(self, caller_number_hash: str) -> CallerHint:
        ...


class TruecallerHintAdapter:
    """Real adapter stub. Disabled unless TRUECALLER_ENABLED=true and a key
    is configured; capability is unconfirmed per architecture section 16.3."""

    def __init__(self) -> None:
        self.enabled = env_bool("TRUECALLER_ENABLED", False)
        self.api_key = env("TRUECALLER_API_KEY", "")

    def lookup(self, caller_number_hash: str) -> CallerHint:
        if not self.enabled or not self.api_key:
            return CallerHint(source="unavailable", spam_hint_0_1=None, label=None, is_mock=False)
        # Real SDK/API integration would go here; left unimplemented because
        # the capability (spam lookup by hashed number) is unconfirmed.
        return CallerHint(source="unavailable", spam_hint_0_1=None, label=None, is_mock=False)


class MockCallerHintAdapter:
    """Deterministic mock for demos; always discloses is_mock=True."""

    def __init__(self, known_spam_hashes: Optional[set] = None) -> None:
        self.known_spam_hashes = known_spam_hashes or set()

    def lookup(self, caller_number_hash: str) -> CallerHint:
        if caller_number_hash in self.known_spam_hashes:
            return CallerHint(source="mock", spam_hint_0_1=0.8, label="reported_spam", is_mock=True)
        return CallerHint(source="mock", spam_hint_0_1=0.1, label="no_reports", is_mock=True)


def get_default_caller_hint_adapter() -> CallerHintAdapter:
    real = TruecallerHintAdapter()
    if real.enabled and real.api_key:
        return real
    return MockCallerHintAdapter()
