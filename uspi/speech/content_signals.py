"""STT + content-risk signals (C14, architecture section 5.9, shared with
live call V2 per section 6).

Content signals (requests for OTP/PIN/password, urgent payment demands,
institution impersonation, suspicious links/instructions) are reported as
unvalidated unless a classifier with its own labels/validation exists.
Here they are produced via the shared Cline client, which is exactly the
"classifier" the architecture leaves as future-validated work -- so the
signal is explicitly marked MODEL_SCORE (never calibrated_probability)
until a held-out validation run promotes it.
"""
from __future__ import annotations

from typing import List, Optional

from uspi.common.cline_client import ClineClient, get_client
from uspi.common.schema import Channel, ScoreSemantics, Signal

SYSTEM_PROMPT = """You analyse a short transcript chunk from a phone call \
or voice note for scam CONTENT risk only (not voice authenticity). Flag: \
requests for password/PIN/OTP, urgent payment demands, impersonation of a \
bank/government/courier/tech-support, requests to move to another app, \
suspicious links or instructions, or pressure/threats. Return STRICT JSON. \
This is a content signal, not proof of fraud. Never state that a person \
is a scammer; describe the behaviour requested in the transcript."""

JSON_SCHEMA = {
    "type": "object",
    "required": ["content_risk_category", "risk_score", "confidence", "tags"],
    "properties": {
        "content_risk_category": {
            "type": "string",
            "enum": ["low", "medium", "high", "inconclusive"],
        },
        "risk_score": {"type": "number", "minimum": 0, "maximum": 1},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "tags": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
    },
}

FALLBACK = {
    "content_risk_category": "inconclusive",
    "risk_score": 0.5,
    "confidence": 0.0,
    "tags": [],
    "rationale": "Cline API unavailable; content risk unavailable, not a safety claim.",
}


class ContentRiskAnalyser:
    def __init__(self, client: Optional[ClineClient] = None) -> None:
        self.client = client or get_client()

    def analyse_chunk(
        self,
        case_id: str,
        channel: Channel,
        transcript_text: str,
        start_s: float,
        end_s: float,
        segment_id: Optional[str] = None,
    ) -> Signal:
        """`segment_id` ties this signal back to the exact STT/refined
        transcript segment it was computed from (architecture-wide id +
        timestamp traceability requirement), recorded in `evidence_ids`."""
        result = self.client.call_structured(
            component="CONTENT_RISK",
            system_prompt=SYSTEM_PROMPT,
            user_payload={"transcript_chunk": transcript_text, "segment_id": segment_id},
            json_schema=JSON_SCHEMA,
            fallback=FALLBACK,
        )
        data = result.data
        semantics = (
            ScoreSemantics.UNAVAILABLE
            if result.used_fallback or data.get("content_risk_category") == "inconclusive"
            else ScoreSemantics.CATEGORICAL
        )
        return Signal(
            name="content_risk",
            version="1.0",
            case_id=case_id,
            channel=channel,
            value=float(data.get("risk_score", 0.5)),
            score_semantics=semantics,
            confidence=float(data.get("confidence", 0.0)),
            window_start_s=start_s,
            window_end_s=end_s,
            evidence_ids=[segment_id] if segment_id else [],
            rationale=data.get("rationale"),
            model_version=result.model_id,
            latency_ms=result.latency_ms,
            extra={
                "content_risk_category": data.get("content_risk_category", "inconclusive"),
                "tags": data.get("tags", []),
                "used_fallback": result.used_fallback,
                "segment_id": segment_id,
            },
        )
