"""Branch A: AASIST adapter (C10, architecture section 5.5).

The architecture calls for vendoring the official AASIST model and
training/evaluating it. Per the task instructions, that trained model is
replaced by a structured Cline API call: the backend sends only
window-level acoustic *descriptors* (duration, energy stats, spectral
summary — never raw audio) to Cline and asks it to produce a spoof-
likelihood "model_score" signal with the same orientation (higher = more
spoof-like) that the real AASIST branch would have produced. This keeps
the adapter interface identical to what a real AASIST wrapper would
expose, so swapping in a real model later only touches this file.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from uspi.common.cline_client import ClineClient, get_client
from uspi.common.schema import Channel, ScoreSemantics, Signal

SYSTEM_PROMPT = """You are standing in for an AASIST-style spectro-temporal \
anti-spoofing acoustic classifier. You receive ONLY aggregate acoustic \
descriptors for a short audio window (duration, RMS energy stats, \
zero-crossing rate, spectral centroid/flatness summaries, no raw audio or \
transcript). Return STRICT JSON with a spoof_likelihood in [0,1] where \
higher means more likely to be synthetic/replayed/spoofed speech, plus a \
confidence and short rationale referencing only the given descriptors. \
If descriptors indicate very low quality / short audio, say so and lower \
confidence rather than guessing."""

JSON_SCHEMA = {
    "type": "object",
    "required": ["spoof_likelihood", "confidence"],
    "properties": {
        "spoof_likelihood": {"type": "number", "minimum": 0, "maximum": 1},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "rationale": {"type": "string"},
    },
}

FALLBACK = {
    "spoof_likelihood": 0.5,
    "confidence": 0.0,
    "rationale": "Cline API unavailable; neutral fallback, not spoof evidence.",
}


def _acoustic_descriptors(samples: np.ndarray, sample_rate: int) -> Dict[str, float]:
    if len(samples) == 0:
        return {"rms": 0.0, "zcr": 0.0, "duration_s": 0.0}
    rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
    zero_crossings = np.sum(np.diff(np.signbit(samples)))
    zcr = float(zero_crossings) / max(len(samples) - 1, 1)
    spectrum = np.abs(np.fft.rfft(samples.astype(np.float64)))
    freqs = np.fft.rfftfreq(len(samples), d=1.0 / sample_rate)
    centroid = float(np.sum(freqs * spectrum) / max(np.sum(spectrum), 1e-9))
    flatness = float(
        np.exp(np.mean(np.log(spectrum + 1e-9))) / max(np.mean(spectrum), 1e-9)
    )
    return {
        "rms": rms,
        "zcr": zcr,
        "duration_s": len(samples) / float(sample_rate),
        "spectral_centroid_hz": centroid,
        "spectral_flatness": flatness,
    }


class AasistAdapter:
    """Interface-compatible stand-in for the official AASIST wrapper."""

    model_version = "aasist-cline-proxy-1.0"

    def __init__(self, client: Optional[ClineClient] = None) -> None:
        self.client = client or get_client()

    def score_window(
        self, case_id: str, samples: np.ndarray, sample_rate: int, start_s: float, end_s: float
    ) -> Signal:
        descriptors = _acoustic_descriptors(samples, sample_rate)
        quality_flags = []
        if descriptors["duration_s"] < 1.0:
            quality_flags.append("short_audio")
        if sample_rate <= 8000:
            quality_flags.append("phone_band")

        result = self.client.call_structured(
            component="VOICE_AASIST",
            system_prompt=SYSTEM_PROMPT,
            user_payload={"descriptors": descriptors, "window": {"start_s": start_s, "end_s": end_s}},
            json_schema=JSON_SCHEMA,
            fallback=FALLBACK,
        )
        data = result.data
        return Signal(
            name="aasist_spoof",
            version="1.0",
            case_id=case_id,
            channel=Channel.RECORDED_VOICE,
            value=float(data.get("spoof_likelihood", 0.5)),
            score_semantics=ScoreSemantics.UNAVAILABLE if result.used_fallback else ScoreSemantics.MODEL_SCORE,
            confidence=float(data.get("confidence", 0.0)),
            window_start_s=start_s,
            window_end_s=end_s,
            quality_flags=quality_flags,
            rationale=data.get("rationale"),
            model_version=f"{self.model_version}:{result.model_id}",
            latency_ms=result.latency_ms,
            extra={"used_fallback": result.used_fallback},
        )
