from uspi.common.schema import Channel, ScoreSemantics, Signal
from uspi.fusion.engine import FusionPolicyEngine


def _signal(name, value, semantics):
    return Signal(name=name, case_id="case1", channel=Channel.TEXT, value=value, score_semantics=semantics)


def test_fusion_engine_masks_non_probability_signals():
    engine = FusionPolicyEngine()
    signals = [
        _signal("stage3_slm_chat_suspicion", 0.9, ScoreSemantics.CALIBRATED_PROBABILITY),
        _signal("aasist_spoof", 0.95, ScoreSemantics.MODEL_SCORE),
    ]
    output = engine.run(
        case_id="case1", channel=Channel.TEXT, signals=signals,
        user_hash="user1", day_bucket="2026-10-10",
    )
    assert "aasist_spoof" in output.stacked.masked_signal_names
    assert output.case_report.tier in {"tier2_warn", "tier3_pause"}


def test_fusion_engine_handles_no_signals_neutrally():
    engine = FusionPolicyEngine()
    output = engine.run(
        case_id="case2", channel=Channel.TEXT, signals=[],
        user_hash="user2", day_bucket="2026-10-10",
    )
    assert output.stacked.probability_estimate == 0.5
    assert output.case_report.tier == "tier1_info"
