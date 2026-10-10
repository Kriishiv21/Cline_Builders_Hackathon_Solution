"""Recorded voice (V1) pipeline orchestrator (architecture section 5.1).

validate -> mono 16kHz -> VAD -> windows -> Branch A (AASIST/Cline) +
Branch B (phonetic/Cline) -> calibration/fusion -> smoothing/intervals ->
shared speech pipeline (STT -> refinement, by segment id/timestamp) ->
content signals (Cline, keyed to the refined segment id) -> risk engine ->
report. The same `uspi.speech.pipeline.SpeechPipeline` instance type is
used on the live-call track (`uspi.live.pipeline.LiveCallPipeline`), so STT
+ refinement behave identically and stay in sync on both input tracks.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from uspi.common.hashing import new_case_id
from uspi.common.schema import CaseReport, Channel, Signal
from uspi.speech.content_signals import ContentRiskAnalyser
from uspi.speech.pipeline import SpeechPipeline
from uspi.voice.aasist_adapter import AasistAdapter
from uspi.voice.audio_prep import load_waveform_specs, simple_vad, to_model_waveform, validate_waveform, windowize
from uspi.voice.calibration import ScoreFusion
from uspi.voice.intervals import IntervalDetector, WindowScore
from uspi.voice.phonetic_adapter import PhoneticAdapter
from uspi.voice.report import build_voice_report
from uspi.voice.risk_engine import VoiceRiskEngine


class RecordedVoicePipeline:
    def __init__(
        self,
        aasist: Optional[AasistAdapter] = None,
        phonetic: Optional[PhoneticAdapter] = None,
        fusion: Optional[ScoreFusion] = None,
        interval_detector: Optional[IntervalDetector] = None,
        content_analyser: Optional[ContentRiskAnalyser] = None,
        speech_pipeline: Optional[SpeechPipeline] = None,
        risk_engine: Optional[VoiceRiskEngine] = None,
        window_s: float = 4.0,
        hop_s: float = 2.0,
    ) -> None:
        self.aasist = aasist or AasistAdapter()
        self.phonetic = phonetic or PhoneticAdapter()
        self.fusion = fusion or ScoreFusion()
        self.interval_detector = interval_detector or IntervalDetector()
        self.content_analyser = content_analyser or ContentRiskAnalyser()
        self.speech_pipeline = speech_pipeline or SpeechPipeline()
        self.risk_engine = risk_engine or VoiceRiskEngine()
        self.window_s = window_s
        self.hop_s = hop_s
        self.specs = load_waveform_specs()

    def analyse(self, samples: np.ndarray, sample_rate: int, case_id: Optional[str] = None) -> CaseReport:
        case_id = case_id or new_case_id("voice")
        quality = validate_waveform(samples, sample_rate)
        speech_segments = simple_vad(samples, sample_rate)
        windows = windowize(samples, sample_rate, self.window_s, self.hop_s)

        signals: List[Signal] = []
        window_scores: List[WindowScore] = []

        for w in windows:
            chunk = w["samples"]
            aasist_sig = self.aasist.score_window(case_id, chunk, sample_rate, w["start_s"], w["end_s"])
            signals.append(aasist_sig)

            vowel_segments = [chunk] if len(chunk) > 256 else []
            phonetic_sig = self.phonetic.score_window(case_id, vowel_segments, sample_rate, w["start_s"], w["end_s"])
            signals.append(phonetic_sig)

            aasist_val = aasist_sig.value if aasist_sig.score_semantics.value != "unavailable" else None
            phonetic_val = phonetic_sig.value if phonetic_sig.score_semantics.value != "unavailable" else None
            fused, provenance = self.fusion.fuse(aasist_val, phonetic_val)
            window_scores.append(
                WindowScore(
                    start_s=w["start_s"], end_s=w["end_s"], fused_score=fused,
                    provenance=provenance, quality_flags=aasist_sig.quality_flags + phonetic_sig.quality_flags,
                )
            )

        intervals = self.interval_detector.detect(window_scores)

        # Shared STT -> refinement step (id'd, timestamped), identical to
        # the one used on the live-call track, so content-risk evidence is
        # always keyed to a stable segment_id on both input tracks.
        transcript_segments = self.speech_pipeline.transcribe_audio(
            case_id, samples, sample_rate, Channel.RECORDED_VOICE
        )
        content_scores = []
        transcript_excerpts = []
        for seg in transcript_segments:
            text = seg.best_text()
            if not text.strip():
                continue
            sig = self.content_analyser.analyse_chunk(
                case_id, Channel.RECORDED_VOICE, text, seg.start_s, seg.end_s, segment_id=seg.segment_id
            )
            signals.append(sig)
            content_scores.append(sig.value if sig.score_semantics.value != "unavailable" else None)
            transcript_excerpts.append({
                "segment_id": seg.segment_id,
                "start_s": seg.start_s,
                "end_s": seg.end_s,
                "raw_text": seg.raw_text,
                "refined_text": seg.refined_text,
                "refinement_status": seg.refinement_status,
                "text": text,
            })

        content_scores = [c for c in content_scores if c is not None]
        avg_content = sum(content_scores) / len(content_scores) if content_scores else None

        mean_fused = (
            sum(w.fused_score for w in window_scores) / len(window_scores) if window_scores else None
        )
        low_confidence = "short_audio" in quality.quality_flags or len(windows) == 0
        risk_result = self.risk_engine.compute(mean_fused, avg_content, None, low_confidence)

        config_versions = {
            "voice_fusion": self.fusion.config_version,
            "voice_risk": self.risk_engine.config_version,
        }
        return build_voice_report(
            case_id=case_id,
            duration_s=quality.duration_s,
            quality_flags=quality.quality_flags,
            risk_result=risk_result,
            signals=signals,
            intervals=intervals,
            transcript_excerpts=transcript_excerpts,
            config_versions=config_versions,
        )
