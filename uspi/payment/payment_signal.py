"""Payment-signal merge (C26, architecture section 2.2, optional).

Deterministic UPI/payment-intent risk scoring, merged into the entity
layer like any other enrichment signal.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PaymentIntent:
    payee_upi_hint: str
    amount: float
    direction: str  # "pay" | "collect"
    first_time_payee: bool


def payment_risk_score(intent: PaymentIntent) -> float:
    score = 0.0
    if intent.direction == "collect":
        score += 0.3  # collect requests are more often used in scams
    if intent.first_time_payee:
        score += 0.3
    if intent.amount >= 10000:
        score += 0.2
    return min(score, 1.0)
