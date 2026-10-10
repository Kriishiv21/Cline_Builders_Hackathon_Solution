"""Shared speech pipeline: STT -> refinement, by segment id/timestamp.

This is the single component both the live-audio input track (V2) and the
audio-recording input track (V1) call to go from raw audio/ASR output to
refined, id'd `TranscriptSegment`s. Keeping one implementation guarantees
the two tracks stay in sync with every step that comes after (content-risk
signal, live analyser, fusion evidence_ids, voice/live report), matching
the reference `meeting_assistant` pipeline's STT -> refine -> minutes
chain, applied per architecture section 5.9 ("STT and content signals")
and section 6 (live call transcript chunks).
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from uspi.common.schema import Channel, TranscriptSegment
from uspi.speech.refine import TranscriptRefiner
from uspi.speech.stt_adapter import MockSTTAdapter, STTAdapter


class SpeechPipeline:
    """`transcribe_audio` is for the two audio-bearing tracks (recorded
    voice windows, or a live-call audio chunk when raw audio is available).
    `refine_external_transcript` is for inputs that arrive as text only
    (e.g. a live telephony transcript chunk pushed by an external STT
    system) -- both paths converge on the same `TranscriptRefiner`, so
    refinement behaviour (guard, model routing, ids) is identical either
    way.
    """

    def __init__(self, stt: Optional[STTAdapter] = None, refiner: Optional[TranscriptRefiner] = None) -> None:
        self.stt = stt or MockSTTAdapter()
        self.refiner = refiner or TranscriptRefiner()

    def transcribe_audio(
        self, case_id: str, samples: np.ndarray, sample_rate: int, channel: Channel
    ) -> List[TranscriptSegment]:
        raw_segments = self.stt.transcribe(case_id, samples, sample_rate, channel)
        return self._refine_nonempty(raw_segments)

    def refine_external_transcript(
        self, case_id: str, segment: TranscriptSegment
    ) -> TranscriptSegment:
        refined = self._refine_nonempty([segment])
        return refined[0] if refined else segment

    def _refine_nonempty(self, segments: List[TranscriptSegment]) -> List[TranscriptSegment]:
        """Refinement is only run on segments with text; empty/unavailable
        ASR output (e.g. silence) is passed through unchanged so the
        pipeline never fabricates content over silence."""
        with_text = [s for s in segments if s.raw_text.strip()]
        refined = self.refiner.refine(with_text) if with_text else []
        by_id = {s.segment_id: s for s in refined}
        return [by_id.get(s.segment_id, s) for s in segments]
