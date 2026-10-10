"""Signal bus (architecture section 2.1/14): collects Signal objects for a
case so the fusion engine and bandit never import feature-specific code.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from uspi.common.schema import Signal


class SignalBus:
    def __init__(self) -> None:
        self._signals: Dict[str, List[Signal]] = defaultdict(list)

    def publish(self, signal: Signal) -> None:
        self._signals[signal.case_id].append(signal)

    def publish_many(self, signals: List[Signal]) -> None:
        for s in signals:
            self.publish(s)

    def get(self, case_id: str) -> List[Signal]:
        return list(self._signals.get(case_id, []))

    def latest_by_name(self, case_id: str) -> Dict[str, Signal]:
        latest: Dict[str, Signal] = {}
        for s in self._signals.get(case_id, []):
            if s.name not in latest or s.ts_utc >= latest[s.name].ts_utc:
                latest[s.name] = s
        return latest

    def clear(self, case_id: str) -> None:
        self._signals.pop(case_id, None)
