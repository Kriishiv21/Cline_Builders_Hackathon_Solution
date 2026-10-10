from uspi.common.schema import CanonicalEvent, EventType
from uspi.text.pipeline import TextPipeline


def test_text_pipeline_runs_slm_on_money_trigger(stub_cline_client):
    stub_cline_client.canned_response["TEXT_SLM"] = {
        "chat_suspicion_probability": 0.8,
        "scam_type_guess": "otp_phishing",
        "per_message_scores": [{"message_index": 0, "suspicion": 0.9}],
        "confidence": 0.7,
        "calibration_status": "calibrated",
        "rationale": "Requests OTP urgently.",
    }
    pipeline = TextPipeline()
    event = CanonicalEvent(
        event_id="c1:1", chat_id="chat1", seq=1, event_type=EventType.MESSAGE,
        ts_utc=1000.0, text="Please share your OTP now, urgent, pay now",
    )
    result = pipeline.process_event(event)
    assert result.ran_slm is True
    assert result.slm_signal is not None
    assert result.slm_signal.value == 0.8
    assert result.funnel_stage in {"LINK_OR_PAYMENT", "PRESSURE"}


def test_negation_suppresses_otp_hit():
    from uspi.text.lexicon import Lexicon
    lex = Lexicon()
    result = lex.score("never share your otp code with anyone")
    assert result.category_weight("otp") == 0.0


def test_trust_badge_tripwire_suspends():
    from uspi.text.trust_badge import TrustBadgeManager
    tb = TrustBadgeManager()
    tb.grant("chat1")
    reason = tb.apply_tripwire("chat1", "please whitelist me now", [])
    assert reason is not None
    assert tb.status("chat1").suspended is True
