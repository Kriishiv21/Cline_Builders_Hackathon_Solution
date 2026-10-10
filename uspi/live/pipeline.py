"""Live call (V2) pipeline orchestrator (architecture section 6).

Per chunk: shared speech pipeline (STT -> refinement, by segment id/
timestamp, identical to the recorded-voice track) -> RAG hint retrieval ->
Cline live analyser (keyed to the refined segment id) -> caller hint prior
-> lookalike check -> call risk engine (hysteresis) -> optional
authenticity scoring (separate field, never folded into call_risk).

Two chunk entry points, both ending up at `_score_segment` so refinement
and everything after it behaves identically either way:
  - `process_audio_chunk`: raw audio is available (e.g. a WebRTC/simulator
    capture of the call) -> runs STT, then refinement.
  - `process_chunk`: only transcript text is available (e.g. a telephony
    STT system pushes text chunks) -> skips STT, still runs refinement on
    the externally supplied text through the same `SpeechPipeline`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from uspi.common.hashing import new_segment_id
from uspi.common.schema import Channel, Signal, TranscriptSegment
from uspi.live.analyser_client import LiveAnalyserClient
from uspi.live.authenticity_adapter import LiveAuthenticityAdapter
from uspi.live.call_risk_engine import CallRiskEngine
from uspi.live.caller_hint import CallerHintAdapter, get_default_caller_hint_adapter
from uspi.live.rag_store import ScamPatternStore
from uspi.speech.pipeline import SpeechPipeline


@dataclass
class LiveChunkResult:
    case_id: str
    segment_id: str
    policy_score: float
    alert_active: bool
    critical: bool
    analyser_signal: Signal
    authenticity_signal: Optional[Signal]
    matched_pattern_ids: List[str]
    novel_pattern: bool
    refinement_status: str


class LiveCallPipeline:
    def __init__(
        self,
        analyser: Optional[LiveAnalyserClient] = None,
        rag_store: Optional[ScamPatternStore] = None,
        risk_engine: Optional[CallRiskEngine] = None,
        caller_hint_adapter: Optional[CallerHintAdapter] = None,
        authenticity_adapter: Optional[LiveAuthenticityAdapter] = None,
        speech_pipeline: Optional[SpeechPipeline] = None,
    ) -> None:
        self.analyser = analyser or LiveAnalyserClient()
        self.rag_store = rag_store or ScamPatternStore()
        self.risk_engine = risk_engine or CallRiskEngine()
        self.caller_hint_adapter = caller_hint_adapter or get_default_caller_hint_adapter()
        self.authenticity_adapter = authenticity_adapter or LiveAuthenticityAdapter(mock_mode=True)
        self.speech_pipeline = speech_pipeline or SpeechPipeline()
        self._caller_hints: dict = {}
        self._chunk_index: dict = {}

    def start_call(self, case_id: str, caller_number_hash: Optional[str] = None) -> None:
        if caller_number_hash:
            self._caller_hints[case_id] = self.caller_hint_adapter.lookup(caller_number_hash)
        self._chunk_index[case_id] = 0

    def process_audio_chunk(
        self, case_id: str, audio_samples: np.ndarray, sample_rate: int, start_s: float, end_s: float
    ) -> List[LiveChunkResult]:
        """Live-audio input track: raw audio -> shared STT -> refinement ->
        one `LiveChunkResult` per STT segment found in this audio chunk."""
        segments = self.speech_pipeline.transcribe_audio(case_id, audio_samples, sample_rate, Channel.LIVE_CALL)
        results = []
        for seg in segments:
            # Offset STT-local timestamps by this chunk's absolute start_s
            # so ids/timestamps stay unique and ordered across chunks.
            seg = seg.model_copy(update={
                "start_s": start_s + seg.start_s, "end_s": start_s + seg.end_s,
                "segment_id": new_segment_id(case_id, start_s + seg.start_s, start_s + seg.end_s,
                                              self._next_index(case_id)),
            })
            if not seg.best_text().strip():
                continue
            results.append(self._score_segment(case_id, seg, audio_samples, sample_rate))
        return results

    def process_chunk(
        self,
        case_id: str,
        transcript_text: str,
        start_s: float,
        end_s: float,
        audio_samples: Optional[np.ndarray] = None,
        sample_rate: int = 16000,
    ) -> LiveChunkResult:
        """Audio-recording-style text input track: an externally supplied
        transcript chunk (e.g. telephony STT) is still run through the
        shared refinement step before analysis, by segment id/timestamp,
        so this path stays in sync with `process_audio_chunk`."""
        seg = TranscriptSegment(
            segment_id=new_segment_id(case_id, start_s, end_s, self._next_index(case_id)),
            case_id=case_id,
            channel=Channel.LIVE_CALL,
            start_s=start_s,
            end_s=end_s,
            raw_text=transcript_text,
        )
        refined_seg = self.speech_pipeline.refine_external_transcript(case_id, seg)
        return self._score_segment(case_id, refined_seg, audio_samples, sample_rate)

    def _next_index(self, case_id: str) -> int:
        idx = self._chunk_index.get(case_id, 0)
        self._chunk_index[case_id] = idx + 1
        return idx

    def _score_segment(
        self,
        case_id: str,
        seg: TranscriptSegment,
        audio_samples: Optional[np.ndarray],
        sample_rate: int,
    ) -> LiveChunkResult:
        text = seg.best_text()
        hints = self.rag_store.top_matches(text)
        caller_hint = self._caller_hints.get(case_id)

        analyser_signal = self.analyser.analyse_chunk(
            case_id, text, seg.start_s, seg.end_s, hints,
            caller_hint.__dict__ if caller_hint else None,
            segment_id=seg.segment_id,
        )

        lookalikes = {p["id"] for p in self.rag_store.lookalikes()}
        matched_ids = set(analyser_signal.extra.get("matched_pattern_ids", []))
        lookalike_match = bool(matched_ids & lookalikes) and not analyser_signal.extra.get("novel_pattern", False)

        spam_hint = caller_hint.spam_hint_0_1 if caller_hint else None
        risk = self.risk_engine.ingest_chunk_risk(
            case_id, analyser_signal.value, spam_hint, lookalike_match
        )

        authenticity_signal = self.authenticity_adapter.score_chunk(
            case_id, audio_samples, sample_rate, seg.start_s, seg.end_s
        )

        return LiveChunkResult(
            case_id=case_id,
            segment_id=seg.segment_id,
            policy_score=risk["policy_score"],
            alert_active=risk["alert_active"],
            critical=risk["critical"],
            analyser_signal=analyser_signal,
            authenticity_signal=authenticity_signal,
            matched_pattern_ids=list(matched_ids),
            novel_pattern=analyser_signal.extra.get("novel_pattern", False),
            refinement_status=seg.refinement_status,
        )

    def end_call(self, case_id: str) -> dict:
        return self.risk_engine.end_of_call_summary(case_id)
