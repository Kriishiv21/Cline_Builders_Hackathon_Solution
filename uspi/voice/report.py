"""Recorded-voice report builder (architecture section 5.11).

No example scores or timestamps are hardcoded here; everything comes from
the caller's computed signals/intervals/risk result.
"""
from __future__ import annotations

from typing import List, Optional

from uspi.common.hashing import new_recording_id
from uspi.common.schema import CaseReport, Channel, Signal
from uspi.voice.intervals import SuspiciousInterval
from uspi.voice.risk_engine import VoiceRiskResult

NEXT_STEPS = {
    "low": "Low risk indicators were found. This is not a guarantee of safety; "
    "stay alert to requests for money, OTPs or moving to another app.",
    "medium": "Review the highlighted sections and verify any unusual requests "
    "independently through a trusted channel before acting.",
    "high": "Do not act on suspicious requests in this recording until you verify "
    "them independently through a trusted, known channel.",
    "inconclusive": "Audio quality or available signals were insufficient for a "
    "confident assessment. Obtain clearer audio or request human review.",
}


def build_voice_report(
    case_id: str,
    duration_s: float,
    quality_flags: List[str],
    risk_result: VoiceRiskResult,
    signals: List[Signal],
    intervals: List[SuspiciousInterval],
    transcript_excerpts: List[dict],
    config_versions: dict,
    recording_id: Optional[str] = None,
) -> CaseReport:
    recording_id = recording_id or new_recording_id()
    reasons = []
    for sig in signals:
        if sig.rationale:
            reasons.append(f"{sig.name}: {sig.rationale}")

    limitations = [
        "Voice authenticity scores are model scores, not calibrated probabilities, "
        "unless calibration has been validated on held-out data for this configuration.",
        "This report never proves identity, liveness, or fraud; it is risk evidence only.",
    ]
    if "phone_band" in quality_flags:
        limitations.append("Audio appears to be telephony band-limited (<=8kHz); "
                            "scores may be less reliable than on clean audio.")
    if "short_audio" in quality_flags:
        limitations.append("Audio is very short; confidence is reduced.")

    flagged_windows = [
        {"start_s": iv.start_s, "end_s": iv.end_s, "peak_score": iv.peak_score, "window_count": iv.window_count}
        for iv in intervals
    ]

    return CaseReport(
        case_id=case_id,
        channel=Channel.RECORDED_VOICE,
        overall_category=risk_result.overall_category,
        tier=risk_result.overall_category,
        calibrated_probability=None,
        policy_score=risk_result.r_overall,
        signals=signals,
        flagged_windows=flagged_windows,
        warning_text=NEXT_STEPS.get(risk_result.overall_category, NEXT_STEPS["inconclusive"]),
        reasons=reasons,
        limitations=limitations,
        config_versions=config_versions,
        uncertainty_note=(
            "Renormalized over available signals." if risk_result.renormalized else None
        ),
    )
