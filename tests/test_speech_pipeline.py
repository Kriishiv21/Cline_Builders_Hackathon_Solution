import numpy as np

from uspi.common.hashing import new_segment_id
from uspi.common.schema import Channel, TranscriptSegment
from uspi.speech.pipeline import SpeechPipeline
from uspi.speech.refine import TranscriptRefiner
from uspi.speech.stt_adapter import MockSTTAdapter


class FixedTextSTT:
    """Deterministic STT stand-in returning a fixed raw transcript, so the
    refinement component has non-empty text to correct."""

    def __init__(self, text: str) -> None:
        self.text = text

    def transcribe(self, case_id, samples, sample_rate, channel):
        duration_s = len(samples) / float(sample_rate) if sample_rate else 0.0
        return [TranscriptSegment(
            segment_id=new_segment_id(case_id, 0.0, duration_s, 0),
            case_id=case_id, channel=channel, start_s=0.0, end_s=duration_s,
            raw_text=self.text, asr_confidence=0.6,
        )]


def test_stt_segment_has_stable_id_and_timestamps():
    stt = MockSTTAdapter()
    samples = np.zeros(16000, dtype=np.float32)
    segs1 = stt.transcribe("case1", samples, 16000, Channel.RECORDED_VOICE)
    segs2 = stt.transcribe("case1", samples, 16000, Channel.RECORDED_VOICE)
    assert segs1[0].segment_id == segs2[0].segment_id  # deterministic by (case, window, index)
    assert segs1[0].start_s == 0.0 and segs1[0].end_s == 1.0


def test_refinement_applies_edit_within_guard(stub_cline_client):
    stt = FixedTextSTT("plees share your otp naw")
    pipeline = SpeechPipeline(stt=stt, refiner=TranscriptRefiner())
    samples = np.zeros(16000, dtype=np.float32)
    expected_id = new_segment_id("case1", 0.0, 1.0, 0)

    stub_cline_client.canned_response["REFINEMENT"] = {
        "segments": [{"segment_id": expected_id, "refined_text": "please share your otp now",
                      "reason": "fixed typos"}]
    }
    segments = pipeline.transcribe_audio("case1", samples, 16000, Channel.RECORDED_VOICE)
    assert len(segments) == 1
    seg = segments[0]
    assert seg.refinement_status == "applied"
    assert seg.best_text() == "please share your otp now"
    assert seg.raw_text == "plees share your otp naw"


def test_refinement_guard_rejects_wild_rewrite(stub_cline_client):
    stt = FixedTextSTT("please share your otp now")
    pipeline = SpeechPipeline(stt=stt, refiner=TranscriptRefiner())
    samples = np.zeros(16000, dtype=np.float32)
    expected_id = new_segment_id("case1", 0.0, 1.0, 0)

    stub_cline_client.canned_response["REFINEMENT"] = {
        "segments": [{"segment_id": expected_id,
                      "refined_text": "completely unrelated invented sentence about weather",
                      "reason": "hallucinated"}]
    }
    segments = pipeline.transcribe_audio("case1", samples, 16000, Channel.RECORDED_VOICE)
    seg = segments[0]
    assert seg.refinement_status == "rejected_by_guard"
    assert seg.best_text() == "please share your otp now"  # raw text kept


def test_refinement_fallback_keeps_text_unchanged(stub_cline_client):
    """With no REFINEMENT canned response registered, the stub echoes the
    fallback (raw_text unchanged) -- the refiner must never fabricate text
    when it has nothing better to say."""
    stt = FixedTextSTT("hello there")
    pipeline = SpeechPipeline(stt=stt, refiner=TranscriptRefiner())
    samples = np.zeros(16000, dtype=np.float32)
    segments = pipeline.transcribe_audio("case1", samples, 16000, Channel.RECORDED_VOICE)
    seg = segments[0]
    assert seg.best_text() == "hello there"
    assert seg.refinement_status in {"unchanged", "unavailable"}


def test_silence_segment_skips_refinement(stub_cline_client):
    """Empty ASR text (silence) must never be sent to the refiner / Cline,
    and must never be fabricated into content."""
    pipeline = SpeechPipeline(stt=MockSTTAdapter(), refiner=TranscriptRefiner())
    samples = np.zeros(16000, dtype=np.float32)
    segments = pipeline.transcribe_audio("case1", samples, 16000, Channel.RECORDED_VOICE)
    assert len(segments) == 1
    assert segments[0].raw_text == ""
    assert segments[0].best_text() == ""
    assert not stub_cline_client.calls  # refiner never called for empty text
