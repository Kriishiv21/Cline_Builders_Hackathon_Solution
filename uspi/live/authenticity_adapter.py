"""Live voice-authenticity adapter (C20, architecture section 6).

Reuses the AASIST/Cline adapter (C10/C09) for authenticity scoring during
a live call. A pure-mock mode is available for demos when live audio
streaming isn't wired up (cut-order item, section 15: "live authenticity
model (use a mock)"). Always kept as a separate field from call_risk, per
the score semantics registry (section 3.4): "voice_authenticity (live):
Model score plus confidence. Separate field, never folded into call_risk."
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from uspi.common.schema import Channel, ScoreSemantics, Signal
from uspi.voice.aasist_adapter import AasistAdapter


class LiveAuthenticityAdapter:
    def __init__(self, aasist: Optional[AasistAdapter] = None, mock_mode: bool = False) -> None:
        self.aasist = aasist or AasistAdapter()
        self.mock_mode = mock_mode

    def score_chunk(self, case_id: str, samples: Optional[np.ndarray], sample_rate: int, start_s: float, end_s: float) -> Signal:
        if self.mock_mode or samples is None or len(samples) == 0:
            return Signal(
                name="voice_authenticity",
                version="1.0",
                case_id=case_id,
                channel=Channel.LIVE_CALL,
                value=0.5,
                score_semantics=ScoreSemantics.UNAVAILABLE,
                confidence=0.0,
                window_start_s=start_s,
                window_end_s=end_s,
                rationale="Mock mode / no audio available for this chunk; authenticity not evaluated.",
                model_version="live-authenticity-mock",
                extra={"is_mock": True},
            )
        underlying = self.aasist.score_window(case_id, samples, sample_rate, start_s, end_s)
        return Signal(
            name="voice_authenticity",
            version="1.0",
            case_id=case_id,
            channel=Channel.LIVE_CALL,
            value=underlying.value,
            score_semantics=underlying.score_semantics,
            confidence=underlying.confidence,
            window_start_s=start_s,
            window_end_s=end_s,
            quality_flags=underlying.quality_flags,
            rationale=underlying.rationale,
            model_version=underlying.model_version,
            latency_ms=underlying.latency_ms,
            extra={"is_mock": False, **underlying.extra},
        )
