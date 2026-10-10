"""Transcript refinement component (new, modelled on the reference
`meeting_assistant` pipeline's STT -> refine -> minutes flow: section 5.9
of the architecture only asked for raw STT + content signals; this module
adds the missing middle step -- correcting raw ASR output -- and wires it
by segment id/timestamp so it stays in sync with every step downstream
(content-risk signal, live analyser, fusion evidence, voice/live report).

Like the other components the architecture would otherwise have us train
(a glossary-matching/edit model), refinement here is a single structured
Cline API call per segment batch, not a locally trained model. A
deterministic guard (anti-hallucination check) rejects any "refined" text
that drifts too far from the raw ASR text, so the LLM can fix garbled
words/names but cannot invent new content -- the same "evidence, not
verdicts" / no-unsupported-edits principle the reference app's edit log
embodies (MATCH_SCORE-style guard).
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Dict, List, Optional

from uspi.common.cline_client import ClineClient, get_client
from uspi.common.config import load_yaml
from uspi.common.schema import TranscriptSegment

SYSTEM_PROMPT = """You correct raw speech-to-text output for a phone call \
or voice note, one batch of timestamped segments at a time, each carrying \
a segment_id. Fix obvious ASR mistakes only: garbled words, mis-heard \
names/numbers/amounts, split or merged words, and punctuation. Do NOT add, \
remove, or reinterpret meaning; do NOT fill in words that were not said; \
do NOT invent names, amounts, OTPs or instructions that are not clearly \
implied by the raw text. If a segment needs no change, return it \
unchanged. Return STRICT JSON: one object per input segment_id, in the \
same order, each with a refined_text field and a short reason."""

JSON_SCHEMA = {
    "type": "object",
    "required": ["segments"],
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["segment_id", "refined_text"],
                "properties": {
                    "segment_id": {"type": "string"},
                    "refined_text": {"type": "string"},
                    "reason": {"type": "string"},
                },
            },
        }
    },
}


def _fallback_for(segments: List[TranscriptSegment]) -> dict:
    """On any Cline failure, refined_text == raw_text (status becomes
    'unavailable' downstream) -- never block the pipeline on refinement."""
    return {
        "segments": [
            {"segment_id": s.segment_id, "refined_text": s.raw_text, "reason": "refinement unavailable"}
            for s in segments
        ]
    }


@dataclass
class RefinementConfig:
    min_similarity_ratio: float
    max_segments_per_call: int
    config_version: str


def _load_config(config_path: str = "refinement.yaml") -> RefinementConfig:
    cfg = load_yaml(config_path)
    return RefinementConfig(
        min_similarity_ratio=cfg.get("min_similarity_ratio", 0.55),
        max_segments_per_call=cfg.get("max_segments_per_call", 20),
        config_version=cfg.get("_config_version", "unversioned"),
    )


class TranscriptRefiner:
    """Batches segments (by id) into bounded-size Cline calls and applies a
    similarity guard before accepting any refined text."""

    def __init__(self, client: Optional[ClineClient] = None, config_path: str = "refinement.yaml") -> None:
        self.client = client or get_client()
        self.config = _load_config(config_path)

    def refine(self, segments: List[TranscriptSegment]) -> List[TranscriptSegment]:
        if not segments:
            return []
        refined: List[TranscriptSegment] = []
        batch_size = self.config.max_segments_per_call
        for start in range(0, len(segments), batch_size):
            refined.extend(self._refine_batch(segments[start : start + batch_size]))
        return refined

    def _refine_batch(self, batch: List[TranscriptSegment]) -> List[TranscriptSegment]:
        payload = {
            "segments": [
                {"segment_id": s.segment_id, "start_s": s.start_s, "end_s": s.end_s, "raw_text": s.raw_text}
                for s in batch
            ]
        }
        result = self.client.call_structured(
            component="REFINEMENT",
            system_prompt=SYSTEM_PROMPT,
            user_payload=payload,
            json_schema=JSON_SCHEMA,
            fallback=_fallback_for(batch),
        )
        by_id: Dict[str, dict] = {item["segment_id"]: item for item in result.data.get("segments", [])}

        out: List[TranscriptSegment] = []
        for seg in batch:
            item = by_id.get(seg.segment_id)
            if result.used_fallback or item is None:
                out.append(seg.model_copy(update={
                    "refined_text": seg.raw_text,
                    "refinement_status": "unavailable",
                    "refinement_model_id": result.model_id,
                }))
                continue

            candidate = item.get("refined_text", seg.raw_text)
            ratio = difflib.SequenceMatcher(None, seg.raw_text.strip().lower(),
                                            candidate.strip().lower()).ratio() if seg.raw_text else 1.0
            if seg.raw_text and ratio < self.config.min_similarity_ratio:
                # Guard: refusal to accept a rewrite that drifted too far
                # from the raw ASR text -- treated as a rejected edit, raw
                # text is kept, never silently replaced with LLM invention.
                out.append(seg.model_copy(update={
                    "refined_text": seg.raw_text,
                    "refinement_status": "rejected_by_guard",
                    "refinement_edits": [{
                        "segment_id": seg.segment_id, "candidate": candidate,
                        "similarity_ratio": ratio, "reason": "below min_similarity_ratio guard",
                    }],
                    "refinement_model_id": result.model_id,
                }))
                continue

            status = "applied" if candidate.strip() != seg.raw_text.strip() else "unchanged"
            out.append(seg.model_copy(update={
                "refined_text": candidate,
                "refinement_status": status,
                "refinement_edits": (
                    [{"segment_id": seg.segment_id, "before": seg.raw_text, "after": candidate,
                      "similarity_ratio": ratio, "reason": item.get("reason", "")}]
                    if status == "applied" else []
                ),
                "refinement_model_id": result.model_id,
            }))
        return out
