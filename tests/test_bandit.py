from uspi.bandit.action_registry import ActionId
from uspi.bandit.context_schema import BanditContext
from uspi.bandit.integration_adapter import BanditIntegrationAdapter
from uspi.bandit.policy_manager import PolicyMode
from uspi.bandit.reward_calculator import OutcomeLabel
from uspi.bandit.safety_constraints import ConstraintContext, constrained_eligible_actions


def test_safety_constraints_block_all_when_no_consent():
    ctx = ConstraintContext(current_tier="tier3_pause", alert_budget_remaining=5,
                             trust_badge_active=False, is_minor_account=False, consent_local_scanning=False)
    actions = constrained_eligible_actions(ctx)
    assert actions == [ActionId.NO_ACTION]


def test_minor_account_cannot_get_no_action_at_tier2():
    ctx = ConstraintContext(current_tier="tier2_warn", alert_budget_remaining=5,
                             trust_badge_active=False, is_minor_account=True, consent_local_scanning=True)
    actions = constrained_eligible_actions(ctx)
    assert ActionId.NO_ACTION not in actions


def test_integration_adapter_baseline_mode():
    adapter = BanditIntegrationAdapter()
    context = BanditContext(case_id="c1", channel="T", probability_estimate=0.7, current_tier="tier2_warn")
    decision = adapter.decide(context)
    assert decision.decided_by == "baseline"
    assert decision.action_id in {ActionId.SHOW_WARNING}


def test_integration_adapter_promoted_mode_uses_bandit():
    adapter = BanditIntegrationAdapter()
    adapter.policy_manager.promote()
    context = BanditContext(case_id="c1", channel="T", probability_estimate=0.7, current_tier="tier2_warn")
    decision = adapter.decide(context)
    assert decision.decided_by == "bandit"


def test_record_outcome_updates_ledger_and_bandit():
    adapter = BanditIntegrationAdapter()
    context = BanditContext(case_id="c1", channel="T", probability_estimate=0.7, current_tier="tier2_warn")
    outcome = OutcomeLabel(verified=True, was_scam=True)
    reward = adapter.record_outcome(context, ActionId.SHOW_WARNING, outcome, provenance="real")
    assert reward > 0
    assert len(adapter.ledger.verified_entries()) == 1


def test_unverified_outcome_never_rewards_detection_accuracy():
    adapter = BanditIntegrationAdapter()
    context = BanditContext(case_id="c1", channel="T", probability_estimate=0.7, current_tier="tier2_warn")
    outcome = OutcomeLabel(verified=False, was_scam=None)
    reward = adapter.record_outcome(context, ActionId.SHOW_WARNING, outcome, provenance="simulation")
    # Only burden cost applies (negative), never a positive detection reward.
    assert reward <= 0
