import numpy as np

from uspi.voice.pipeline import RecordedVoicePipeline


def test_voice_pipeline_handles_short_silent_audio(stub_cline_client):
    stub_cline_client.canned_response["VOICE_AASIST"] = {"spoof_likelihood": 0.5, "confidence": 0.1}
    stub_cline_client.canned_response["VOICE_PHONETIC"] = {
        "spoof_likelihood": 0.5, "confidence": 0.0, "status": "insufficient_vowels"
    }
    pipeline = RecordedVoicePipeline()
    samples = np.zeros(16000 * 2, dtype=np.float32)  # 2s silence
    report = pipeline.analyse(samples, 16000)
    assert report.overall_category in {"low", "medium", "high", "inconclusive"}
    assert report.channel.value == "V1"


def test_voice_pipeline_scores_normal_speech_like_audio(stub_cline_client):
    stub_cline_client.canned_response["VOICE_AASIST"] = {"spoof_likelihood": 0.2, "confidence": 0.6}
    stub_cline_client.canned_response["VOICE_PHONETIC"] = {
        "spoof_likelihood": 0.3, "confidence": 0.5, "status": "scored"
    }
    pipeline = RecordedVoicePipeline()
    t = np.linspace(0, 4, 16000 * 4, endpoint=False)
    samples = (0.3 * np.sin(2 * np.pi * 180 * t)).astype(np.float32)
    report = pipeline.analyse(samples, 16000)
    assert isinstance(report.policy_score, float)
    assert len(report.signals) > 0


def test_formant_insufficient_vowels_never_spoof_evidence(stub_cline_client):
    from uspi.voice.phonetic_adapter import PhoneticAdapter
    adapter = PhoneticAdapter()
    sig = adapter.score_window("case1", [], 16000, 0.0, 1.0)
    assert sig.score_semantics.value == "unavailable"
    assert sig.value == 0.5


def test_voice_pipeline_content_signal_is_keyed_to_refined_segment_id(stub_cline_client):
    """The recorded-voice track's content-risk signal must carry the same
    segment_id the shared speech pipeline assigned to the STT/refined
    transcript segment, so it stays traceable through fusion and the
    report -- the same contract the live-call track uses."""
    from uspi.common.hashing import new_segment_id
    from uspi.common.schema import Channel, TranscriptSegment
    from uspi.speech.pipeline import SpeechPipeline
    from uspi.speech.refine import TranscriptRefiner
    from uspi.voice.pipeline import RecordedVoicePipeline

    class FixedTextSTT:
        def transcribe(self, case_id, samples, sample_rate, channel):
            duration_s = len(samples) / float(sample_rate) if sample_rate else 0.0
            return [TranscriptSegment(
                segment_id=new_segment_id(case_id, 0.0, duration_s, 0),
                case_id=case_id, channel=channel, start_s=0.0, end_s=duration_s,
                raw_text="please share your otp now", asr_confidence=0.7,
            )]

    stub_cline_client.canned_response["VOICE_AASIST"] = {"spoof_likelihood": 0.3, "confidence": 0.5}
    stub_cline_client.canned_response["VOICE_PHONETIC"] = {
        "spoof_likelihood": 0.3, "confidence": 0.5, "status": "scored"
    }
    stub_cline_client.canned_response["CONTENT_RISK"] = {
        "content_risk_category": "high", "risk_score": 0.9, "confidence": 0.8,
        "tags": ["otp_request"], "rationale": "Requests OTP.",
    }

    speech_pipeline = SpeechPipeline(stt=FixedTextSTT(), refiner=TranscriptRefiner())
    pipeline = RecordedVoicePipeline(speech_pipeline=speech_pipeline, window_s=4.0, hop_s=4.0)
    samples = np.zeros(16000 * 4, dtype=np.float32)
    report = pipeline.analyse(samples, 16000)

    content_signals = [s for s in report.signals if s.name == "content_risk"]
    assert len(content_signals) == 1
    expected_id = new_segment_id(report.case_id, 0.0, 4.0, 0)
    assert content_signals[0].evidence_ids == [expected_id]
    assert content_signals[0].extra["segment_id"] == expected_id
