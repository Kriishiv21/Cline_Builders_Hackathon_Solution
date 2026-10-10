"""Deterministic replay harness for canonical events.

Section 15 phase 0 exit criterion: "a recorded chat replays deterministically".
"""
from __future__ import annotations

from typing import Callable, List

from uspi.common.schema import CanonicalEvent


class ReplayHarness:
    def __init__(self, events: List[CanonicalEvent]) -> None:
        # order by (chat_id, seq), never wall-clock
        self.events = sorted(events, key=lambda e: (e.chat_id, e.seq))

    def replay(self, on_event: Callable[[CanonicalEvent], None]) -> None:
        for event in self.events:
            on_event(event)

    def checksum(self) -> str:
        import hashlib

        h = hashlib.sha256()
        for e in self.events:
            h.update(e.model_dump_json().encode("utf-8"))
        return h.hexdigest()
