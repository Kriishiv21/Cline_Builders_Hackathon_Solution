"""STT adapter (architecture section 5.9: "candidate: Whisper").

Whisper is a pretrained ASR model, not something this platform trains, so
it is NOT replaced by the Cline API (that substitution only applies to
components the architecture asks us to *train*: AASIST, the phonetic
classifier, the Stage-3 SLM, the content-risk classifier and the live
voice-authenticity adapter). This module defines the adapter interface the
rest of the pipeline depends on; swap `MockSTTAdapter` for a real Whisper
(or hosted STT, e.g. the `faster-whisper` wrapper used by the reference
`meeting_assistant` app) client in production without touching any
downstream code.

Every emitted unit is a `uspi.common.schema.TranscriptSegment` carrying a
stable `segment_id` + timestamps, so the refinement step, content-risk
signal, live analyser and fusion report can all reference the exact same
span across both the recorded-voice (V1) and live-call (V2) input tracks.
"""
from __future__ import annotations

from typing import List, Protocol

import numpy as np

from uspi.common.hashing import new_segment_id
from uspi.common.schema import Channel, TranscriptSegment

# Mirrors the reference app's supported upload formats (meeting_assistant.stt).
SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".mp4", ".flac", ".ogg", ".webm"}


def format_timestamp(seconds: float) -> str:
    """mm:ss(.ss) formatter, matching the reference app's transcript display."""
    seconds = max(0.0, float(seconds))
    minutes, rem = divmod(seconds, 60.0)
    return f"{int(minutes):02d}:{rem:05.2f}" if rem % 1 else f"{int(minutes):02d}:{int(rem):02d}"


class STTAdapter(Protocol):
    def transcribe(
        self, case_id: str, samples: np.ndarray, sample_rate: int, channel: Channel
    ) -> List[TranscriptSegment]:
        ...


class MockSTTAdapter:
    """Deterministic placeholder used in tests/dev when no real STT engine
    is wired up. Never claims a real transcript; callers should treat the
    `asr_confidence` of 0.0 as "no transcript available". Still emits a
    properly id'd/timestamped segment so the rest of the pipeline (ids,
    refinement, downstream signals) can be exercised end to end."""

    def transcribe(
        self, case_id: str, samples: np.ndarray, sample_rate: int, channel: Channel
    ) -> List[TranscriptSegment]:
        duration_s = len(samples) / float(sample_rate) if sample_rate else 0.0
        if duration_s <= 0:
            return []
        return [
            TranscriptSegment(
                segment_id=new_segment_id(case_id, 0.0, duration_s, 0),
                case_id=case_id,
                channel=channel,
                start_s=0.0,
                end_s=duration_s,
                raw_text="",
                asr_confidence=0.0,
            )
        ]


class WhisperSTTAdapter:
    """Thin wrapper around a `faster-whisper`-style model (as loaded by the
    reference `meeting_assistant.stt.load_model`). Not instantiated by
    default (no model bundled here); wire in an already-loaded `model`
    object exposing a `.transcribe(samples, sample_rate)` contract that
    yields objects with `start`, `end`, `text`, `avg_logprob`, then use it
    in place of `MockSTTAdapter` in `RecordedVoicePipeline` / `SpeechPipeline`.
    """

    def __init__(self, model) -> None:
        self.model = model

    def transcribe(
        self, case_id: str, samples: np.ndarray, sample_rate: int, channel: Channel
    ) -> List[TranscriptSegment]:
        raw_segments = self.model.transcribe(samples, sample_rate)  # provider-specific
        segments: List[TranscriptSegment] = []
        for i, seg in enumerate(raw_segments):
            start_s = float(getattr(seg, "start", 0.0))
            end_s = float(getattr(seg, "end", start_s))
            confidence = float(getattr(seg, "avg_logprob", 0.0))
            segments.append(
                TranscriptSegment(
                    segment_id=new_segment_id(case_id, start_s, end_s, i),
                    case_id=case_id,
                    channel=channel,
                    start_s=start_s,
                    end_s=end_s,
                    raw_text=getattr(seg, "text", ""),
                    asr_confidence=confidence,
                )
            )
        return segments
