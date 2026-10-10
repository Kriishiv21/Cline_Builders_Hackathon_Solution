"""FastAPI app (architecture section 13.1/13.2 API contracts).

Exposes:
  POST /v1/text/event        -> process_event (text pipeline)
  POST /v1/voice/analyze     -> recorded-voice report (audio input track;
                                 shared STT -> refinement inside)
  POST /v1/live/start        -> start a live call case
  POST /v1/live/chunk        -> live call, text input track (externally
                                 supplied transcript chunk; still refined)
  POST /v1/live/audio_chunk  -> live call, audio input track (raw audio
                                 chunk; shared STT -> refinement, same
                                 pipeline as /v1/voice/analyze)
  POST /v1/live/end          -> end-of-call summary
  POST /v1/bandit/outcome    -> report_outcome -> feedback ledger
  GET  /healthz              -> health check
"""
from __future__ import annotations

import base64
import time
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel

from uspi.bandit.reward_calculator import OutcomeLabel
from uspi.common.hashing import chat_id_hash, new_case_id
from uspi.common.schema import CanonicalEvent, Channel, EventType
from uspi.fusion.engine import FusionPolicyEngine
from uspi.live.pipeline import LiveCallPipeline
from uspi.text.pipeline import TextPipeline
from uspi.voice.pipeline import RecordedVoicePipeline

app = FastAPI(title="Unified Scam Intelligence Platform", version="0.1.0")

_text_pipeline = TextPipeline()
_voice_pipeline = RecordedVoicePipeline()
_live_pipeline = LiveCallPipeline()
_fusion_engine = FusionPolicyEngine()


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "ts_utc": time.time()}


class TextEventRequest(BaseModel):
    chat_id: str
    seq: int
    text: str = ""
    ts_utc: float
    sender: Optional[str] = None
    event_flags: List[str] = []


@app.post("/v1/text/event")
def process_text_event(req: TextEventRequest) -> dict:
    event = CanonicalEvent(
        event_id=f"{req.chat_id}:{req.seq}",
        chat_id=chat_id_hash(req.chat_id),
        seq=req.seq,
        event_type=EventType.MESSAGE,
        ts_utc=req.ts_utc,
        text=req.text,
        extra={"event_flags": req.event_flags},
    )
    result = _text_pipeline.process_event(event)
    signals = [result.slm_signal] if result.slm_signal else []
    fusion_out = _fusion_engine.run(
        case_id=result.case_id,
        channel=Channel.TEXT,
        signals=signals,
        user_hash=event.chat_id,
        day_bucket=time.strftime("%Y-%m-%d", time.gmtime(req.ts_utc)),
        funnel_stage=result.funnel_stage,
        scam_type_guess=(result.slm_signal.extra.get("scam_type_guess") if result.slm_signal else None),
    )
    return {
        "case_id": fusion_out.case_report.case_id,
        "tier": fusion_out.case_report.tier,
        "calibrated_probability": fusion_out.case_report.calibrated_probability,
        "warning_text": fusion_out.case_report.warning_text,
        "action": fusion_out.action_decision.action_id.value,
        "trust_suspended_reason": result.trust_suspended_reason,
        "t_star_message_index": result.t_star_message_index,
    }


class VoiceAnalyzeRequest(BaseModel):
    pcm16_base64: str
    sample_rate: int = 16000


@app.post("/v1/voice/analyze")
def analyze_voice(req: VoiceAnalyzeRequest) -> dict:
    raw = base64.b64decode(req.pcm16_base64)
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    report = _voice_pipeline.analyse(samples, req.sample_rate)
    return report.model_dump()


class LiveStartRequest(BaseModel):
    caller_number: Optional[str] = None


@app.post("/v1/live/start")
def live_start(req: LiveStartRequest) -> dict:
    case_id = new_case_id("live")
    caller_hash = chat_id_hash(req.caller_number) if req.caller_number else None
    _live_pipeline.start_call(case_id, caller_hash)
    return {"case_id": case_id}


class LiveChunkRequest(BaseModel):
    case_id: str
    transcript_text: str
    start_s: float
    end_s: float


def _chunk_result_payload(result) -> dict:
    return {
        "case_id": result.case_id,
        "segment_id": result.segment_id,
        "policy_score": result.policy_score,
        "alert_active": result.alert_active,
        "critical": result.critical,
        "scam_type_guess": result.analyser_signal.extra.get("scam_type_guess"),
        "novel_pattern": result.novel_pattern,
        "matched_pattern_ids": result.matched_pattern_ids,
        "voice_authenticity": result.authenticity_signal.value if result.authenticity_signal else None,
        "refinement_status": result.refinement_status,
    }


@app.post("/v1/live/chunk")
def live_chunk(req: LiveChunkRequest) -> dict:
    """Audio-recording-style text input track (architecture section 6):
    an externally supplied transcript chunk, still refined by segment id
    before analysis (uspi.live.pipeline.LiveCallPipeline.process_chunk)."""
    result = _live_pipeline.process_chunk(req.case_id, req.transcript_text, req.start_s, req.end_s)
    return _chunk_result_payload(result)


class LiveAudioChunkRequest(BaseModel):
    case_id: str
    pcm16_base64: str
    sample_rate: int = 16000
    start_s: float


@app.post("/v1/live/audio_chunk")
def live_audio_chunk(req: LiveAudioChunkRequest) -> dict:
    """Live-audio input track (architecture section 6): raw audio bytes for
    one chunk of an ongoing call -> shared STT -> refinement -> scoring,
    kept in sync with /v1/voice/analyze via the same `SpeechPipeline`."""
    raw = base64.b64decode(req.pcm16_base64)
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    end_s = req.start_s + (len(samples) / float(req.sample_rate) if req.sample_rate else 0.0)
    results = _live_pipeline.process_audio_chunk(req.case_id, samples, req.sample_rate, req.start_s, end_s)
    return {"segments": [_chunk_result_payload(r) for r in results]}


@app.post("/v1/live/end")
def live_end(case_id: str) -> dict:
    return _live_pipeline.end_call(case_id)


class BanditOutcomeRequest(BaseModel):
    case_id: str
    action_id: str
    verified: bool
    was_scam: Optional[bool] = None
    user_overrode_alert: bool = False


@app.post("/v1/bandit/outcome")
def bandit_outcome(req: BanditOutcomeRequest) -> dict:
    from uspi.bandit.action_registry import ActionId
    from uspi.bandit.context_schema import BanditContext

    outcome = OutcomeLabel(
        verified=req.verified, was_scam=req.was_scam, user_overrode_alert=req.user_overrode_alert
    )
    ctx = BanditContext(
        case_id=req.case_id, channel="T", probability_estimate=0.5, current_tier="tier1_info",
    )
    reward = _fusion_engine.bandit_adapter.record_outcome(ctx, ActionId(req.action_id), outcome)
    return {"reward": reward}
