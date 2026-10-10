"""Branch B: phonetic/formant adapter (C11, architecture section 5.6).

The architecture trains a logistic-regression classifier on F1/F2/F3
formant features from vowel segments. Per the task instructions, that
trained classifier is replaced by a Cline API call: formant measurements
(extracted deterministically here via a lightweight LPC-based formant
estimator) are sent to Cline, which returns a spoof-likelihood judgement
grounded only in the numeric formant/quality descriptors it is given.
Quality filters still run locally: too few usable vowels => 'unavailable',
never spoof evidence (architecture rule, section 5.6).
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from uspi.common.cline_client import ClineClient, get_client
from uspi.common.schema import Channel, ScoreSemantics, Signal

SYSTEM_PROMPT = """You are standing in for a phonetic/formant-based \
anti-spoofing classifier (trained on F1/F2/F3 vowel formants in the \
source literature). You receive ONLY a list of formant measurements \
(F1/F2/F3 in Hz) for vowel segments in one audio window, plus the usable- \
vowel fraction and declared formant ceiling used. Return STRICT JSON with \
spoof_likelihood in [0,1], higher = more spoof-like (formant patterns \
atypical of genuine human vocal-tract resonance), and confidence. If \
usable_vowel_fraction is low, you MUST return spoof_likelihood 0.5 and \
confidence 0 with status "insufficient_vowels" rather than guessing; this \
is required because low quality must never be treated as spoof evidence."""

JSON_SCHEMA = {
    "type": "object",
    "required": ["spoof_likelihood", "confidence", "status"],
    "properties": {
        "spoof_likelihood": {"type": "number", "minimum": 0, "maximum": 1},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "status": {"type": "string", "enum": ["scored", "insufficient_vowels"]},
        "rationale": {"type": "string"},
    },
}

FALLBACK = {
    "spoof_likelihood": 0.5,
    "confidence": 0.0,
    "status": "insufficient_vowels",
    "rationale": "Cline API unavailable; neutral fallback, not spoof evidence.",
}

MIN_USABLE_VOWEL_FRACTION = 0.3


def estimate_formants_lpc(samples: np.ndarray, sample_rate: int, n_formants: int = 3) -> Optional[List[float]]:
    """Very lightweight LPC-based formant estimator for vowel-like frames.
    Not a validated clinical/forensic formant tracker; used only to produce
    numeric descriptors for the Cline-backed judgement (never for a direct
    rule-based spoof decision)."""
    if len(samples) < 256:
        return None
    windowed = samples * np.hamming(len(samples))
    order = 2 + sample_rate // 1000
    try:
        a = _lpc(windowed, order)
    except Exception:
        return None
    roots = np.roots(a)
    roots = roots[np.imag(roots) >= 0]
    angles = np.arctan2(np.imag(roots), np.real(roots))
    freqs = angles * (sample_rate / (2 * np.pi))
    freqs = sorted(f for f in freqs if 90 < f < sample_rate / 2)
    if len(freqs) < n_formants:
        return None
    return freqs[:n_formants]


def _lpc(x: np.ndarray, order: int) -> np.ndarray:
    autocorr = np.correlate(x, x, mode="full")[len(x) - 1 :]
    autocorr = autocorr[: order + 1]
    R = autocorr
    a = np.zeros(order + 1)
    a[0] = 1.0
    e = R[0]
    for i in range(1, order + 1):
        acc = R[i] + np.dot(a[1:i], R[i - 1 : 0 : -1])
        k = -acc / e if e != 0 else 0.0
        a_new = a.copy()
        for j in range(1, i):
            a_new[j] = a[j] + k * a[i - j]
        a_new[i] = k
        a = a_new
        e *= 1 - k ** 2
    return a


class PhoneticAdapter:
    model_version = "phonetic-cline-proxy-1.0"

    def __init__(self, client: Optional[ClineClient] = None, formant_ceiling_hz: float = 5000.0) -> None:
        self.client = client or get_client()
        self.formant_ceiling_hz = formant_ceiling_hz

    def score_window(
        self,
        case_id: str,
        vowel_segments: List[np.ndarray],
        sample_rate: int,
        start_s: float,
        end_s: float,
    ) -> Signal:
        all_formants: List[List[float]] = []
        for seg in vowel_segments:
            formants = estimate_formants_lpc(seg, sample_rate)
            if formants:
                all_formants.append(formants)

        usable_fraction = len(all_formants) / len(vowel_segments) if vowel_segments else 0.0
        quality_flags = []
        if usable_fraction < MIN_USABLE_VOWEL_FRACTION:
            quality_flags.append("insufficient_usable_vowels")
            return Signal(
                name="phonetic_spoof",
                version="1.0",
                case_id=case_id,
                channel=Channel.RECORDED_VOICE,
                value=0.5,
                score_semantics=ScoreSemantics.UNAVAILABLE,
                confidence=0.0,
                window_start_s=start_s,
                window_end_s=end_s,
                quality_flags=quality_flags,
                rationale="Too few usable vowels; not evaluated (never treated as spoof evidence).",
                model_version=self.model_version,
                extra={"usable_vowel_fraction": usable_fraction},
            )

        result = self.client.call_structured(
            component="VOICE_PHONETIC",
            system_prompt=SYSTEM_PROMPT,
            user_payload={
                "formants_hz": all_formants,
                "usable_vowel_fraction": usable_fraction,
                "formant_ceiling_hz": self.formant_ceiling_hz,
            },
            json_schema=JSON_SCHEMA,
            fallback=FALLBACK,
        )
        data = result.data
        semantics = ScoreSemantics.UNAVAILABLE if (
            result.used_fallback or data.get("status") == "insufficient_vowels"
        ) else ScoreSemantics.MODEL_SCORE
        return Signal(
            name="phonetic_spoof",
            version="1.0",
            case_id=case_id,
            channel=Channel.RECORDED_VOICE,
            value=float(data.get("spoof_likelihood", 0.5)),
            score_semantics=semantics,
            confidence=float(data.get("confidence", 0.0)),
            window_start_s=start_s,
            window_end_s=end_s,
            quality_flags=quality_flags,
            rationale=data.get("rationale"),
            model_version=f"{self.model_version}:{result.model_id}",
            latency_ms=result.latency_ms,
            extra={"usable_vowel_fraction": usable_fraction, "used_fallback": result.used_fallback},
        )
