"""Feedback ledger (C23, architecture sections 8, 12.1).

Hashed, consent-gated records of (context, action, outcome). Provenance
(verified vs simulated) is always stored, per section 12.2: "Simulation
labelled separately from real verified outcomes."
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

from uspi.bandit.action_registry import ActionId
from uspi.bandit.reward_calculator import OutcomeLabel


@dataclass
class LedgerEntry:
    case_id: str
    action_id: str
    reward: float
    verified: bool
    was_scam: Optional[bool]
    provenance: str  # "real" | "simulation"
    ts_utc: float
    config_versions: dict


class FeedbackLedger:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path
        self._entries: List[LedgerEntry] = []

    def record(
        self,
        case_id: str,
        action_id: ActionId,
        reward: float,
        outcome: OutcomeLabel,
        provenance: str,
        config_versions: dict,
    ) -> LedgerEntry:
        entry = LedgerEntry(
            case_id=case_id,
            action_id=action_id.value,
            reward=reward,
            verified=outcome.verified,
            was_scam=outcome.was_scam,
            provenance=provenance,
            ts_utc=time.time(),
            config_versions=config_versions,
        )
        self._entries.append(entry)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(entry)) + "\n")
        return entry

    def verified_entries(self) -> List[LedgerEntry]:
        return [e for e in self._entries if e.verified and e.provenance == "real"]

    def simulation_entries(self) -> List[LedgerEntry]:
        return [e for e in self._entries if e.provenance == "simulation"]

    def all_entries(self) -> List[LedgerEntry]:
        return list(self._entries)
