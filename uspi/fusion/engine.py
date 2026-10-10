"""Fusion + policy engine (C21, architecture section 2.1 L4): case-level
stacker -> tiers/hysteresis/alert budget -> bandit action decision ->
CaseReport. The single cross-channel decision point.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from uspi.bandit.action_registry import ActionId
from uspi.bandit.context_builder import build_context
from uspi.bandit.integration_adapter import ActionDecision, BanditIntegrationAdapter
from uspi.common.schema import CaseReport, Channel, Signal
from uspi.fusion.policy_tiers import PolicyTierEngine, TierDecision
from uspi.fusion.stacker import CaseStacker, StackedResult

WARNING_TEXT = {
    "tier0_none": "No notable risk indicators found. This is not a guarantee of safety.",
    "tier1_info": "Some risk indicators were found. Review the highlighted content.",
    "tier2_warn": "Several risk indicators suggest this may be a scam attempt. Do not "
    "share OTPs, passwords, or money, and verify requests independently.",
    "tier3_pause": "Strong risk indicators detected. Pause before acting: verify through "
    "a trusted, known channel before sharing information or money.",
}


@dataclass
class FusionOutput:
    case_report: CaseReport
    stacked: StackedResult
    tier_decision: TierDecision
    action_decision: ActionDecision


class FusionPolicyEngine:
    def __init__(
        self,
        stacker: Optional[CaseStacker] = None,
        tier_engine: Optional[PolicyTierEngine] = None,
        bandit_adapter: Optional[BanditIntegrationAdapter] = None,
    ) -> None:
        self.stacker = stacker or CaseStacker()
        self.tier_engine = tier_engine or PolicyTierEngine()
        self.bandit_adapter = bandit_adapter or BanditIntegrationAdapter()

    def run(
        self,
        case_id: str,
        channel: Channel,
        signals: List[Signal],
        user_hash: str,
        day_bucket: str,
        funnel_stage: Optional[str] = None,
        trust_badge_active: bool = False,
        novel_pattern: bool = False,
        seen_on_n_channels: int = 1,
        is_minor_account: bool = False,
        consent_local_scanning: bool = True,
        scam_type_guess: Optional[str] = None,
    ) -> FusionOutput:
        stacked = self.stacker.stack(signals)
        tier_decision = self.tier_engine.decide(user_hash, stacked.probability_estimate, day_bucket)

        bandit_context = build_context(
            case_id=case_id,
            channel=channel.value,
            probability_estimate=stacked.probability_estimate,
            current_tier=tier_decision.tier,
            funnel_stage=funnel_stage,
            trust_badge_active=trust_badge_active,
            novel_pattern=novel_pattern,
            seen_on_n_channels=seen_on_n_channels,
            alert_budget_remaining=tier_decision.alert_budget_remaining,
            is_minor_account=is_minor_account,
            consent_local_scanning=consent_local_scanning,
        )
        action_decision = self.bandit_adapter.decide(bandit_context)

        case_report = CaseReport(
            case_id=case_id,
            channel=channel,
            overall_category=tier_decision.tier,
            scam_type_guess=scam_type_guess,
            tier=tier_decision.tier,
            calibrated_probability=stacked.probability_estimate,
            policy_score=None,
            signals=signals,
            warning_text=WARNING_TEXT.get(tier_decision.tier, WARNING_TEXT["tier0_none"]),
            reasons=[s.rationale for s in signals if s.rationale],
            limitations=[
                "This report is risk evidence, not a verdict. A human must make the final call.",
            ],
            config_versions={
                "fusion": self.stacker.config_version,
                "tiers": self.tier_engine.config_version,
            },
            uncertainty_note=(
                f"Masked (non-probability) signals: {', '.join(stacked.masked_signal_names)}"
                if stacked.masked_signal_names else None
            ),
        )
        return FusionOutput(
            case_report=case_report, stacked=stacked, tier_decision=tier_decision,
            action_decision=action_decision,
        )
