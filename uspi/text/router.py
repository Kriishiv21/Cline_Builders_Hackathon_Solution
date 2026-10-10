"""Router + context assembler (architecture section 4.4, C07).

Router runs the SLM when a trigger fires, every N_c messages, or with
probability epsilon + kappa * entropy of the previous score. A chat is
never skipped permanently. Assembler packs a bounded token budget using
event-indexed packing so padding attacks cannot push the scam out of the
window.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from uspi.common.config import load_yaml

TRIGGER_FLAGS = {
    "has_link", "money_ask", "otp_ask", "platform_shift", "dormancy_burst", "tripwire",
}


@dataclass
class ChatRouterState:
    chat_id: str
    messages_since_last_run: int = 0
    last_score: Optional[float] = None


class Router:
    def __init__(self, config_path: str = "router.yaml", rng: Optional[random.Random] = None) -> None:
        cfg = load_yaml(config_path)
        self.n_c = cfg.get("periodic_n_c", 10)
        self.epsilon = cfg.get("epsilon", 0.05)
        self.kappa = cfg.get("kappa", 0.5)
        self.token_budget = cfg.get("token_budget", 384)
        self.exemplar_count = cfg.get("scam_exemplar_count", 3)
        self.config_version = cfg.get("_config_version", "unversioned")
        self._states: Dict[str, ChatRouterState] = {}
        self._rng = rng or random.Random(0)

    def _state(self, chat_id: str) -> ChatRouterState:
        return self._states.setdefault(chat_id, ChatRouterState(chat_id=chat_id))

    @staticmethod
    def _binary_entropy(p: float) -> float:
        p = min(max(p, 1e-6), 1 - 1e-6)
        return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))

    def should_run_slm(self, chat_id: str, event_flags: List[str]) -> bool:
        state = self._state(chat_id)
        state.messages_since_last_run += 1

        if any(flag in TRIGGER_FLAGS for flag in event_flags):
            self._reset(chat_id)
            return True

        if state.messages_since_last_run >= self.n_c:
            self._reset(chat_id)
            return True

        entropy = self._binary_entropy(state.last_score) if state.last_score is not None else 1.0
        prob = self.epsilon + self.kappa * entropy
        if self._rng.random() < prob:
            self._reset(chat_id)
            return True
        return False

    def _reset(self, chat_id: str) -> None:
        self._states[chat_id].messages_since_last_run = 0

    def record_score(self, chat_id: str, score: float) -> None:
        self._state(chat_id).last_score = score


@dataclass
class AssembledContext:
    chat_id: str
    first_message: Optional[dict]
    last_n_messages: List[dict]
    event_messages: List[dict]
    funnel_state: str
    room1_prior: float
    gnn_prior: float
    scam_exemplars: List[str] = field(default_factory=list)

    def to_prompt_payload(self) -> dict:
        """Event-indexed packing: always keeps first message + event
        messages regardless of padding, so flooding cannot evict them."""
        return {
            "chat_id_hash": self.chat_id,
            "first_message": self.first_message,
            "last_messages": self.last_n_messages,
            "event_messages": self.event_messages,
            "funnel_state": self.funnel_state,
            "room1_prior": self.room1_prior,
            "gnn_prior": self.gnn_prior,
            "scam_exemplars": self.scam_exemplars[: 3],
        }


class ContextAssembler:
    def __init__(self, config_path: str = "router.yaml") -> None:
        cfg = load_yaml(config_path)
        self.last_n = cfg.get("last_n_messages", 20)

    def assemble(
        self,
        chat_id: str,
        messages: List[dict],
        event_messages: List[dict],
        funnel_state: str,
        room1_prior: float,
        gnn_prior: float,
        scam_exemplars: List[str],
    ) -> AssembledContext:
        first_message = messages[0] if messages else None
        last_n_messages = messages[-self.last_n :] if messages else []
        return AssembledContext(
            chat_id=chat_id,
            first_message=first_message,
            last_n_messages=last_n_messages,
            event_messages=event_messages,
            funnel_state=funnel_state,
            room1_prior=room1_prior,
            gnn_prior=gnn_prior,
            scam_exemplars=scam_exemplars,
        )
