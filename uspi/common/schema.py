"""Unified Signal schema (architecture section 3.3) and canonical event
schema (architecture section 3.2).

Every detector, enrichment module and Cline-backed analyser emits a
`Signal`, so the fusion engine (uspi/fusion) and the bandit (uspi/bandit)
never import feature-specific code.
"""
from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class Channel(str, Enum):
    TEXT = "T"
    RECORDED_VOICE = "V1"
    LIVE_CALL = "V2"


class ScoreSemantics(str, Enum):
    CALIBRATED_PROBABILITY = "calibrated_probability"
    MODEL_SCORE = "model_score"
    POLICY_SCORE_0_100 = "policy_score_0_100"
    CATEGORICAL = "categorical"
    UNAVAILABLE = "unavailable"


class Orientation(str, Enum):
    HIGHER_IS_RISK = "higher_is_risk"  # canonical, post-adaptation
    LOWER_IS_RISK = "lower_is_risk"  # raw orientation, pre-adaptation only


class Signal(BaseModel):
    """Unified Signal object (architecture section 3.3)."""

    name: str
    version: str = "1.0"
    case_id: str
    channel: Channel
    value: float = Field(..., description="The score, per score_semantics.")
    score_semantics: ScoreSemantics
    orientation: Orientation = Orientation.HIGHER_IS_RISK
    raw_orientation: Optional[Orientation] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    uncertainty: Optional[float] = Field(None, ge=0.0, le=1.0)
    window_start_s: Optional[float] = None
    window_end_s: Optional[float] = None
    message_ids: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    quality_flags: List[str] = Field(default_factory=list)
    rationale: Optional[str] = None
    model_version: Optional[str] = None
    latency_ms: Optional[float] = None
    ts_utc: float = Field(default_factory=lambda: time.time())
    extra: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("value")
    @classmethod
    def _finite(cls, v: float) -> float:
        if v != v or v in (float("inf"), float("-inf")):  # NaN/Inf guard
            raise ValueError("Signal.value must be finite")
        return v

    def is_usable_in_stacker(self) -> bool:
        """Only calibrated probabilities are usable directly in the stacker
        (score semantics registry, architecture section 3.4)."""
        return self.score_semantics == ScoreSemantics.CALIBRATED_PROBABILITY


# --- Canonical event schema (architecture section 3.2) ---------------------

class EventType(str, Enum):
    MESSAGE = "message"
    EDIT = "edit"
    DELETE = "delete"
    DISAPPEAR = "disappear"
    REACTION = "reaction"
    MEMBER_JOIN = "member_join"
    MEMBER_LEAVE = "member_leave"
    PROFILE_CHANGE = "profile_change"
    CALL_EVENT = "call_event"
    MEDIA = "media"
    AUDIO_ASSET = "audio_asset"
    TRANSCRIPT_CHUNK = "transcript_chunk"


class CanonicalEvent(BaseModel):
    event_id: str
    chat_id: str
    seq: int = Field(..., description="Order by (chat_id, seq), never wall clock.")
    event_type: EventType
    ts_utc: float
    sender_id_hash: Optional[str] = None
    text: Optional[str] = None
    media: Optional[Dict[str, Any]] = None
    # audio_asset: a recording handle, never the bytes
    audio_asset_ref: Optional[str] = None
    # transcript_chunk fields
    start_s: Optional[float] = None
    end_s: Optional[float] = None
    asr_confidence: Optional[float] = None
    capability_flags: List[str] = Field(
        default_factory=list,
        description="e.g. ['cannot_see_outgoing_messages'] so absence of "
        "evidence is never read as safety.",
    )
    extra: Dict[str, Any] = Field(default_factory=dict)


class TranscriptSegment(BaseModel):
    """Shared STT + refinement unit (architecture section 5.9/6, extended
    here with a stable id so every downstream signal, report line and
    fusion evidence_id can trace back to the exact ASR segment it came
    from, across both the recorded-voice (V1) and live-call (V2) tracks).
    """

    segment_id: str
    case_id: str
    channel: Channel
    start_s: float
    end_s: float
    raw_text: str
    refined_text: Optional[str] = None
    asr_confidence: Optional[float] = None
    refinement_status: str = "not_run"  # not_run | unchanged | applied | rejected_by_guard | unavailable
    refinement_edits: List[Dict[str, Any]] = Field(default_factory=list)
    refinement_model_id: Optional[str] = None

    def best_text(self) -> str:
        """The text downstream analysers should use: refined if available
        and accepted, otherwise the raw ASR text (never blocked on
        refinement failing)."""
        return self.refined_text if self.refined_text is not None else self.raw_text


class CaseReport(BaseModel):
    """Top-level output object shared by text, recorded-voice and live
    report builders (architecture sections 4.6, 5.11, 6)."""

    case_id: str
    channel: Channel
    generated_at_utc: float = Field(default_factory=lambda: time.time())
    overall_category: str
    scam_type_guess: Optional[str] = None
    tier: str
    calibrated_probability: Optional[float] = None
    policy_score: Optional[float] = None
    signals: List[Signal] = Field(default_factory=list)
    flagged_windows: List[Dict[str, Any]] = Field(default_factory=list)
    warning_text: str
    reasons: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    config_versions: Dict[str, str] = Field(default_factory=dict)
    uncertainty_note: Optional[str] = None
