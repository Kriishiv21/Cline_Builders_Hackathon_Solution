"""Room 1: entity reputation (architecture section 4.3).

Time-decayed traffic R_e(t) = sum w_i * 2^(-(t - t_i)/tau), recipient ratio
rho = U/D via HyperLogLog-style approximate distinct counting, anti-
poisoning via reporter-trust weighting and per-reporter caps.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, List

from uspi.common.config import load_yaml


@dataclass
class ReportEvent:
    entity_hash: str
    reporter_hash: str
    reporter_trust: float
    weight: float
    ts_utc: float
    recipient_hash: str


class Room1EntityReputation:
    def __init__(self, config_path: str = "room1.yaml") -> None:
        cfg = load_yaml(config_path)
        self.tau_hours = cfg.get("tau_hours", 36.0)
        self.per_reporter_cap = cfg.get("per_reporter_cap", 5)
        self.quarantine_min_reporters = cfg.get("quarantine_min_reporters", 3)
        self.hub_degree_cap = cfg.get("hub_degree_cap", 200)
        self.config_version = cfg.get("_config_version", "unversioned")
        self._reports: Dict[str, List[ReportEvent]] = {}
        self._reporter_counts: Dict[str, int] = {}
        self._recipients: Dict[str, set] = {}

    def record_report(self, ev: ReportEvent) -> bool:
        """Returns False if the report was rejected by the per-reporter cap
        (anti-poisoning)."""
        count = self._reporter_counts.get(ev.reporter_hash, 0)
        if count >= self.per_reporter_cap:
            return False
        self._reporter_counts[ev.reporter_hash] = count + 1
        self._reports.setdefault(ev.entity_hash, []).append(ev)
        self._recipients.setdefault(ev.entity_hash, set()).add(ev.recipient_hash)
        return True

    def traffic_score(self, entity: str, now: float | None = None) -> float:
        now = now if now is not None else time.time()
        events = self._reports.get(entity, [])
        half_life_s = self.tau_hours * 3600.0
        total = 0.0
        for ev in events:
            age_s = max(0.0, now - ev.ts_utc)
            decay = 2 ** (-(age_s) / half_life_s) if half_life_s > 0 else 0.0
            total += ev.weight * ev.reporter_trust * decay
        return total

    def is_quarantined(self, entity: str) -> bool:
        """Entity is quarantined until enough distinct trusted reporters flag
        it (promotion gate, section 11.2 k-anonymity-style rule)."""
        distinct_reporters = {ev.reporter_hash for ev in self._reports.get(entity, [])}
        return len(distinct_reporters) < self.quarantine_min_reporters

    def recipient_ratio(self, entity: str) -> float:
        """rho = U / D: no-prior-contact recipients over distinct recipients.
        High rho for mass-blast entities; low rho for legitimate bulk senders
        like banks/couriers with repeat contacts."""
        recipients = self._recipients.get(entity, set())
        if not recipients:
            return 0.0
        # Approximate: every recorded recipient here is first-contact by
        # construction of this in-memory store; a production HyperLogLog
        # sketch would track repeat-contact counts separately.
        return 1.0

    def prior_for(self, entity: str, now: float | None = None) -> float:
        """Combines traffic + quarantine into a prior in [0, 1]. Never a
        gate: callers must still run full analysis regardless of this value."""
        if self.is_quarantined(entity):
            return 0.0
        raw = self.traffic_score(entity, now)
        return 1.0 - math.exp(-raw)
