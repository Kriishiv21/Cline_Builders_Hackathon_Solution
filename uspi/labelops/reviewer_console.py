"""Reviewer console + label ops (C24, architecture section 2.2/5.2 split
integrity). In-memory queue standing in for a real UI backend; the
reviewer's decision becomes a verified OutcomeLabel for the feedback
ledger.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from uspi.bandit.reward_calculator import OutcomeLabel
from uspi.common.schema import CaseReport


@dataclass
class ReviewQueueItem:
    case_id: str
    report: CaseReport
    reviewer_decision: Optional[OutcomeLabel] = None
    reviewer_hash: Optional[str] = None


class ReviewerConsole:
    def __init__(self) -> None:
        self._queue: Dict[str, ReviewQueueItem] = {}

    def enqueue(self, report: CaseReport) -> None:
        self._queue[report.case_id] = ReviewQueueItem(case_id=report.case_id, report=report)

    def pending(self) -> List[ReviewQueueItem]:
        return [item for item in self._queue.values() if item.reviewer_decision is None]

    def submit_decision(self, case_id: str, reviewer_hash: str, was_scam: bool) -> OutcomeLabel:
        outcome = OutcomeLabel(verified=True, was_scam=was_scam)
        if case_id in self._queue:
            self._queue[case_id].reviewer_decision = outcome
            self._queue[case_id].reviewer_hash = reviewer_hash
        return outcome
