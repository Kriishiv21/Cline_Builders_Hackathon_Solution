"""Ingestion adapters (C01): convert channel-specific inputs into the
canonical event schema (architecture section 3.2).

Each adapter declares capability flags so absence of evidence is never
read as safety.
"""
from __future__ import annotations

import itertools
from typing import Iterable, List

from uspi.common.hashing import sender_id_hash
from uspi.common.schema import CanonicalEvent, EventType

_seq_counter = itertools.count(1)


class ChatExportAdapter:
    """Adapts a generic chat export (list of dict messages) into canonical
    `message` / `edit` / `delete` / `member_join` / `profile_change` events.

    Rules implemented (section 3.2):
      - order by (chat_id, seq), not wall-clock
      - dedup by event_id
      - keep deleted/edited messages as flagged records, not removed
      - declare capability flags
    """

    capability_flags: List[str] = []

    def __init__(self, chat_id: str, capability_flags: List[str] | None = None) -> None:
        self.chat_id = chat_id
        self.capability_flags = capability_flags or []
        self._seen_event_ids: set[str] = set()

    def adapt(self, raw_messages: Iterable[dict]) -> List[CanonicalEvent]:
        events: List[CanonicalEvent] = []
        for raw in raw_messages:
            event_id = raw.get("event_id") or f"{self.chat_id}:{raw.get('id')}"
            if event_id in self._seen_event_ids:
                continue  # dedup by event_id
            self._seen_event_ids.add(event_id)

            raw_type = raw.get("type", "message")
            try:
                event_type = EventType(raw_type)
            except ValueError:
                event_type = EventType.MESSAGE

            sender = raw.get("sender")
            events.append(
                CanonicalEvent(
                    event_id=event_id,
                    chat_id=self.chat_id,
                    seq=raw.get("seq", next(_seq_counter)),
                    event_type=event_type,
                    ts_utc=float(raw.get("ts_utc", 0.0)),
                    sender_id_hash=sender_id_hash(sender) if sender else None,
                    text=raw.get("text"),
                    media=raw.get("media"),
                    capability_flags=self.capability_flags,
                    extra={k: v for k, v in raw.items() if k not in {
                        "event_id", "id", "type", "seq", "ts_utc", "sender", "text", "media",
                    }},
                )
            )
        events.sort(key=lambda e: e.seq)
        return events


class AudioAssetAdapter:
    """Adapts a recorded voice note / call recording handle into an
    `audio_asset` canonical event. Never carries raw bytes."""

    def __init__(self, chat_id: str) -> None:
        self.chat_id = chat_id

    def adapt(self, recording_id: str, duration_s: float, ts_utc: float) -> CanonicalEvent:
        return CanonicalEvent(
            event_id=f"{self.chat_id}:{recording_id}",
            chat_id=self.chat_id,
            seq=next(_seq_counter),
            event_type=EventType.AUDIO_ASSET,
            ts_utc=ts_utc,
            audio_asset_ref=recording_id,
            extra={"duration_s": duration_s},
        )


class TranscriptChunkAdapter:
    """Adapts live-call STT chunks (10-15s) into `transcript_chunk` events."""

    def __init__(self, chat_id: str) -> None:
        self.chat_id = chat_id

    def adapt(
        self, text: str, start_s: float, end_s: float, asr_confidence: float, ts_utc: float
    ) -> CanonicalEvent:
        return CanonicalEvent(
            event_id=f"{self.chat_id}:chunk:{start_s}:{end_s}",
            chat_id=self.chat_id,
            seq=next(_seq_counter),
            event_type=EventType.TRANSCRIPT_CHUNK,
            ts_utc=ts_utc,
            text=text,
            start_s=start_s,
            end_s=end_s,
            asr_confidence=asr_confidence,
        )
