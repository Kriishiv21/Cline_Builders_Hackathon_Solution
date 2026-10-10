"""Adaptive preprocessing agent tools (architecture section 10.3).

Exposes inspect_audio / diarize_audio / score_call as plain Python
functions that a headless `cline -y --json` runtime agent would call as
MCP tools. This file defines the tool contracts and safe defaults; it
does NOT itself change the waveform spec, detector, thresholds or any
pyannote version (architecture constraint).
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from uspi.voice.audio_prep import validate_waveform


def inspect_audio(samples: np.ndarray, sample_rate: int) -> Dict:
    """Always called first by the runtime policy. Returns quality metadata
    only; never alters the audio."""
    q = validate_waveform(samples, sample_rate)
    return {
        "duration_s": q.duration_s,
        "sample_rate": q.sample_rate,
        "quality_flags": q.quality_flags,
    }


def diarize_audio(samples: np.ndarray, sample_rate: int, num_speakers_hint: Optional[int] = None) -> List[Dict]:
    """Placeholder for pyannote/speaker-diarization-3.1 (gated model,
    requires HF_TOKEN). Not vendored here; returns a single-speaker
    fallback span so downstream code has a stable contract to test
    against."""
    duration_s = len(samples) / float(sample_rate) if sample_rate else 0.0
    return [{"speaker_id": "speaker_0", "start_s": 0.0, "end_s": duration_s}]


def score_call(samples: np.ndarray, sample_rate: int) -> Dict:
    """Runs the recorded-voice pipeline end to end for one call/recording.
    The adaptive agent may only choose num_speakers hints, chunk overlap
    and retry/warning wording around this call — never the waveform spec,
    detector, thresholds, or pyannote version."""
    from uspi.voice.pipeline import RecordedVoicePipeline

    pipeline = RecordedVoicePipeline()
    report = pipeline.analyse(samples, sample_rate)
    return report.model_dump()
