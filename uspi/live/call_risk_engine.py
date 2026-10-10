"""Live call risk engine with hysteresis (C17, architecture sections 6, 7
Glossary "Hysteresis": separate raise and clear thresholds so alerts do
not flicker. call_risk is a policy score 0-100, not a probability
(score semantics registry, section 3.4), and is the alert driver for V2
only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from uspi.common.config import load_yaml


@dataclass
class CallState:
    case_id: str
    alert_active: bool = False
    chunk_risk_scores: List[float] = field(default_factory=list)
    spam_prior: float = 0.0
    lookalike_suppression: float = 0.0


class CallRiskEngine:
    def __init__(self, config_path: str = "live_call.yaml") -> None:
        cfg = load_yaml(config_path)
        self.raise_threshold = cfg.get("raise_threshold", 65.0)
        self.clear_threshold = cfg.get("clear_threshold", 40.0)
        self.critical_threshold = cfg.get("critical_threshold", 85.0)
        self.spam_prior_weight = cfg.get("spam_prior_weight", 10.0)
        self.lookalike_max_subtraction = cfg.get("lookalike_max_subtraction", 20.0)
        self.config_version = cfg.get("_config_version", "unversioned")
        self._states: Dict[str, CallState] = {}

    def _state(self, case_id: str) -> CallState:
        return self._states.setdefault(case_id, CallState(case_id=case_id))

    def ingest_chunk_risk(
        self,
        case_id: str,
        chunk_risk_0_1: float,
        spam_hint_0_1: Optional[float] = None,
        lookalike_match: bool = False,
    ) -> dict:
        state = self._state(case_id)
        state.chunk_risk_scores.append(chunk_risk_0_1)
        if spam_hint_0_1 is not None:
            state.spam_prior = spam_hint_0_1

        base_policy_score = 100.0 * chunk_risk_0_1
        prior_boost = self.spam_prior_weight * state.spam_prior
        lookalike_subtraction = self.lookalike_max_subtraction if lookalike_match else 0.0

        policy_score = max(0.0, min(100.0, base_policy_score + prior_boost - lookalike_subtraction))

        if not state.alert_active and policy_score >= self.raise_threshold:
            state.alert_active = True
        elif state.alert_active and policy_score < self.clear_threshold:
            state.alert_active = False

        return {
            "policy_score": policy_score,
            "alert_active": state.alert_active,
            "critical": policy_score >= self.critical_threshold,
            "lookalike_suppressed": lookalike_match,
        }

    def end_of_call_summary(self, case_id: str) -> dict:
        state = self._state(case_id)
        if not state.chunk_risk_scores:
            return {"outcome": "no_alert_raised", "reason": "no_chunks_scored"}
        if state.alert_active:
            return {"outcome": "alert", "reason": "active_at_call_end"}
        max_score = max(state.chunk_risk_scores)
        if max_score < (self.raise_threshold / 100.0):
            # Below threshold for the whole call: logged as 'no alert raised',
            # never 'verified safe' (architecture section 1.2, 16.2 #3).
            return {"outcome": "no_alert_raised", "reason": "below_threshold_whole_call"}
        return {"outcome": "no_alert_raised", "reason": "cleared_before_call_end"}
