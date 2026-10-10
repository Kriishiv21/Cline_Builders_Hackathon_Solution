"""Bandit integration adapter (architecture section 8/14): the single
entry point the fusion/UX layer calls to get the next permitted action,
wiring context building, safety constraints, policy mode (baseline/
shadow/promoted) and the feedback ledger together.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from uspi.bandit.action_registry import ActionId
from uspi.bandit.baseline_policy import baseline_select
from uspi.bandit.context_schema import BanditContext
from uspi.bandit.contextual_bandit import ContextualBandit
from uspi.bandit.feedback_ledger import FeedbackLedger
from uspi.bandit.policy_manager import PolicyManager, PolicyMode
from uspi.bandit.reward_calculator import OutcomeLabel, RewardCalculator
from uspi.bandit.safety_constraints import ConstraintContext, constrained_eligible_actions


@dataclass
class ActionDecision:
    action_id: ActionId
    decided_by: str  # "baseline" | "bandit"
    shadow_bandit_action: Optional[ActionId] = None


class BanditIntegrationAdapter:
    def __init__(
        self,
        bandit: Optional[ContextualBandit] = None,
        policy_manager: Optional[PolicyManager] = None,
        reward_calculator: Optional[RewardCalculator] = None,
        ledger: Optional[FeedbackLedger] = None,
    ) -> None:
        self.bandit = bandit or ContextualBandit()
        self.policy_manager = policy_manager or PolicyManager()
        self.reward_calculator = reward_calculator or RewardCalculator()
        self.ledger = ledger or FeedbackLedger()

    def decide(self, context: BanditContext) -> ActionDecision:
        constraint_ctx = ConstraintContext(
            current_tier=context.current_tier,
            alert_budget_remaining=context.alert_budget_remaining,
            trust_badge_active=context.trust_badge_active,
            is_minor_account=context.is_minor_account,
            consent_local_scanning=context.consent_local_scanning,
        )
        eligible = constrained_eligible_actions(constraint_ctx)
        baseline_action = baseline_select(context)

        if self.policy_manager.mode == PolicyMode.BASELINE_ONLY:
            return ActionDecision(action_id=baseline_action, decided_by="baseline")

        bandit_action = self.bandit.select(context, eligible)
        if self.policy_manager.mode == PolicyMode.SHADOW:
            return ActionDecision(action_id=baseline_action, decided_by="baseline", shadow_bandit_action=bandit_action)

        return ActionDecision(action_id=bandit_action, decided_by="bandit")

    def record_outcome(
        self,
        context: BanditContext,
        action_id: ActionId,
        outcome: OutcomeLabel,
        provenance: str = "real",
    ) -> float:
        reward = self.reward_calculator.compute(action_id, outcome)
        self.bandit.update(context, action_id, reward)
        self.ledger.record(
            case_id=context.case_id,
            action_id=action_id,
            reward=reward,
            outcome=outcome,
            provenance=provenance,
            config_versions={
                "bandit": self.bandit.config_version,
                "reward_calculator": self.reward_calculator.config_version,
            },
        )
        return reward
