"""Stage 3 small attention SLM (architecture section 4.5, C08).

Architecture asks for a trained <=6-layer, d<=256 attention model with
per-message suspicion, chat score, scam-type and calibration heads, plus
entity-feature dropout during training and timestamp localization (t*).

Per the task instructions, the *trained* model is replaced end-to-end by a
single structured Cline API call: the backend sends the assembled,
hashed/redacted context (uspi.text.router.AssembledContext) and asks for
exactly the same output contract the SLM would have produced. All
calibration-status bookkeeping, thresholding and t* localization logic
stay deterministic in this module; only the raw judgement comes from
Cline.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from uspi.common.cline_client import ClineClient, get_client
from uspi.common.config import load_yaml
from uspi.common.schema import ScoreSemantics, Signal, Channel

SYSTEM_PROMPT = """You are the Stage-3 scam-risk analyser for a chat-safety \
platform. You receive a hashed/redacted chat context (no raw phone \
numbers, names or account numbers - only pseudonymous ids) and must return \
STRICT JSON matching the given schema. Score message-level and chat-level \
suspicion of SCAM BEHAVIOUR ONLY (not spam, not rudeness, not opinions). \
Consider: urgency language, requests for OTP/money/off-platform movement, \
authority impersonation, funnel progression, cold-entity engagement. \
Return evidence as message indices, not raw text repeated back. Never \
accuse a person; describe behaviour only. If the context is insufficient, \
return calibration_status="uncalibrated" and a conservative score near 0.5 \
with low confidence rather than guessing confidently."""

JSON_SCHEMA = {
    "type": "object",
    "required": ["chat_suspicion_probability", "scam_type_guess", "per_message_scores", "confidence", "calibration_status"],
    "properties": {
        "chat_suspicion_probability": {"type": "number", "minimum": 0, "maximum": 1},
        "scam_type_guess": {"type": "string"},
        "per_message_scores": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["message_index", "suspicion"],
                "properties": {
                    "message_index": {"type": "integer"},
                    "suspicion": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "calibration_status": {"type": "string", "enum": ["calibrated", "uncalibrated"]},
        "rationale": {"type": "string"},
    },
}

FALLBACK = {
    "chat_suspicion_probability": 0.5,
    "scam_type_guess": "unknown",
    "per_message_scores": [],
    "confidence": 0.0,
    "calibration_status": "uncalibrated",
    "rationale": "Cline API unavailable; returning neutral, low-confidence fallback. "
    "This is NOT a safety determination.",
}


class Stage3SLM:
    def __init__(self, client: Optional[ClineClient] = None, config_path: str = "stage3_slm.yaml") -> None:
        self.client = client or get_client()
        cfg = load_yaml(config_path)
        self.localization_theta = cfg.get("localization_theta", 0.6)
        self.temperature = cfg.get("calibration_temperature", 1.0)
        self.config_version = cfg.get("_config_version", "unversioned")

    def analyse(self, case_id: str, context_payload: Dict[str, Any]) -> Signal:
        result = self.client.call_structured(
            component="TEXT_SLM",
            system_prompt=SYSTEM_PROMPT,
            user_payload=context_payload,
            json_schema=JSON_SCHEMA,
            fallback=FALLBACK,
        )
        data = result.data
        semantics = (
            ScoreSemantics.CALIBRATED_PROBABILITY
            if data.get("calibration_status") == "calibrated" and not result.used_fallback
            else ScoreSemantics.UNAVAILABLE
            if result.used_fallback
            else ScoreSemantics.MODEL_SCORE
        )
        return Signal(
            name="stage3_slm_chat_suspicion",
            version="1.0",
            case_id=case_id,
            channel=Channel.TEXT,
            value=float(data.get("chat_suspicion_probability", 0.5)),
            score_semantics=semantics,
            confidence=float(data.get("confidence", 0.0)),
            rationale=data.get("rationale"),
            model_version=result.model_id,
            latency_ms=result.latency_ms,
            extra={
                "scam_type_guess": data.get("scam_type_guess", "unknown"),
                "per_message_scores": data.get("per_message_scores", []),
                "used_fallback": result.used_fallback,
            },
        )

    def localize_t_star(self, per_message_scores: List[Dict[str, Any]]) -> Optional[int]:
        """t*: first message index from which score stays above theta for
        the rest of the sequence (architecture section 4.5)."""
        scores = sorted(per_message_scores, key=lambda x: x["message_index"])
        for i, item in enumerate(scores):
            if all(s["suspicion"] >= self.localization_theta for s in scores[i:]):
                return item["message_index"]
        return None
