"""Voice risk engine (C15, architecture section 5.10).

R_voice = 100 * p_spoof; R_content = 100 * sum(w_i * c_i);
R_overall = alpha*R_voice + beta*R_content + gamma*R_context.
Missing signals renormalized under documented policy, never zero risk.
Deterministic; weights/thresholds are policy, not probabilities.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from uspi.common.config import load_yaml


@dataclass
class VoiceRiskResult:
    r_voice: Optional[float]
    r_content: Optional[float]
    r_context: Optional[float]
    r_overall: float
    overall_category: str
    renormalized: bool
    weights_used: dict


class VoiceRiskEngine:
    def __init__(self, config_path: str = "voice_risk.yaml") -> None:
        cfg = load_yaml(config_path)
        self.alpha = cfg.get("alpha_voice", 0.5)
        self.beta = cfg.get("beta_content", 0.4)
        self.gamma = cfg.get("gamma_context", 0.1)
        self.low_threshold = cfg.get("category_low_max", 30.0)
        self.medium_threshold = cfg.get("category_medium_max", 60.0)
        self.high_threshold = cfg.get("category_high_max", 100.0)
        self.min_confidence_for_scoring = cfg.get("min_confidence_for_scoring", 0.2)
        self.config_version = cfg.get("_config_version", "unversioned")

    def compute(
        self,
        p_spoof: Optional[float],
        content_risk_0_1: Optional[float],
        context_risk_0_1: Optional[float] = None,
        low_confidence: bool = False,
    ) -> VoiceRiskResult:
        r_voice = 100.0 * p_spoof if p_spoof is not None else None
        r_content = 100.0 * content_risk_0_1 if content_risk_0_1 is not None else None
        r_context = 100.0 * context_risk_0_1 if context_risk_0_1 is not None else None

        components = []
        if r_voice is not None:
            components.append((self.alpha, r_voice))
        if r_content is not None:
            components.append((self.beta, r_content))
        if r_context is not None:
            components.append((self.gamma, r_context))

        renormalized = False
        if not components:
            return VoiceRiskResult(
                r_voice=r_voice, r_content=r_content, r_context=r_context,
                r_overall=0.0, overall_category="inconclusive", renormalized=False,
                weights_used={},
            )

        total_w = sum(w for w, _ in components)
        if total_w < (self.alpha + self.beta + self.gamma) - 1e-9:
            renormalized = True
        r_overall = sum((w / total_w) * v for w, v in components) if total_w > 0 else 0.0

        if low_confidence:
            category = "inconclusive"
        elif r_overall <= self.low_threshold:
            category = "low"
        elif r_overall <= self.medium_threshold:
            category = "medium"
        else:
            category = "high"

        return VoiceRiskResult(
            r_voice=r_voice,
            r_content=r_content,
            r_context=r_context,
            r_overall=r_overall,
            overall_category=category,
            renormalized=renormalized,
            weights_used={"alpha": self.alpha, "beta": self.beta, "gamma": self.gamma},
        )
