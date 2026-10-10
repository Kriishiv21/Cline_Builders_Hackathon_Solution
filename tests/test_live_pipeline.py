import numpy as np

from uspi.common.hashing import new_segment_id
from uspi.live.pipeline import LiveCallPipeline


def test_live_pipeline_lookalike_suppresses_alert(stub_cline_client):
    stub_cline_client.canned_response["LIVE_ANALYSER"] = {
        "risk_score": 0.9, "confidence": 0.8, "scam_type_guess": "otp_phishing",
        "novel_pattern": False, "matched_pattern_ids": ["genuine_bank_otp_alert"],
        "rationale": "Mentions OTP but matches genuine bank alert pattern.",
    }
    pipeline = LiveCallPipeline()
    pipeline.start_call("case1")
    result = pipeline.process_chunk("case1", "Your OTP is 123456, do not share this otp", 0, 12)
    assert result.policy_score < 90  # lookalike subtraction applied
    assert result.segment_id  # text-track chunk is still id'd/refined
    assert result.refinement_status in {"unchanged", "unavailable"}


def test_live_pipeline_text_chunk_is_refined_before_analysis(stub_cline_client):
    """The text input track still runs the shared refinement step, keyed
    by segment id, before the analyser ever sees the transcript."""
    pipeline = LiveCallPipeline()
    pipeline.start_call("case_refine")
    expected_id = new_segment_id("case_refine", 0.0, 12.0, 0)
    stub_cline_client.canned_response["REFINEMENT"] = {
        "segments": [{"segment_id": expected_id, "refined_text": "please share your otp now",
                      "reason": "fixed typo"}]
    }
    stub_cline_client.canned_response["LIVE_ANALYSER"] = {
        "risk_score": 0.5, "confidence": 0.5, "scam_type_guess": "otp_phishing",
        "novel_pattern": False, "matched_pattern_ids": [], "rationale": "ok",
    }
    result = pipeline.process_chunk("case_refine", "plz share yr otp naw", 0, 12)
    assert result.segment_id == expected_id
    assert result.refinement_status == "applied"
    analyser_call = next(c for c in stub_cline_client.calls if c["component"] == "LIVE_ANALYSER")
    assert analyser_call["payload"]["transcript_chunk"] == "please share your otp now"
    assert analyser_call["payload"]["segment_id"] == expected_id


def test_live_pipeline_audio_chunk_track_produces_ided_results(stub_cline_client):
    """Live-audio input track: raw audio -> STT -> refinement -> analysis,
    same pipeline the recorded-voice track uses."""
    pipeline = LiveCallPipeline()
    pipeline.start_call("case_audio")
    stub_cline_client.canned_response["LIVE_ANALYSER"] = {
        "risk_score": 0.2, "confidence": 0.4, "scam_type_guess": "unknown",
        "novel_pattern": False, "matched_pattern_ids": [], "rationale": "quiet",
    }
    samples = np.zeros(16000, dtype=np.float32)  # MockSTTAdapter emits empty text for silence
    results = pipeline.process_audio_chunk("case_audio", samples, 16000, start_s=0.0, end_s=1.0)
    # Silence yields empty ASR text, which is filtered out before scoring,
    # exercising the same "never fabricate over silence" rule as the
    # recorded-voice track.
    assert results == []


def test_live_pipeline_raises_alert_on_high_risk(stub_cline_client):
    stub_cline_client.canned_response["LIVE_ANALYSER"] = {
        "risk_score": 0.95, "confidence": 0.9, "scam_type_guess": "remote_access_scam",
        "novel_pattern": False, "matched_pattern_ids": ["remote_access_request"],
        "rationale": "Asked to install remote access app.",
    }
    pipeline = LiveCallPipeline()
    pipeline.start_call("case2")
    result = pipeline.process_chunk("case2", "please install anydesk now", 0, 12)
    assert result.alert_active is True


def test_live_pipeline_end_of_call_no_alert_not_verified_safe(stub_cline_client):
    stub_cline_client.canned_response["LIVE_ANALYSER"] = {
        "risk_score": 0.1, "confidence": 0.5, "scam_type_guess": "unknown",
        "novel_pattern": False, "matched_pattern_ids": [], "rationale": "Routine chat.",
    }
    pipeline = LiveCallPipeline()
    pipeline.start_call("case3")
    pipeline.process_chunk("case3", "hi how are you", 0, 12)
    summary = pipeline.end_call("case3")
    assert summary["outcome"] == "no_alert_raised"
    assert summary["reason"] != "verified_safe"
