"""Text channel pipeline orchestrator (ScamRoom v5, architecture section 4).

Wires Stage 1 (lexicon/encoder/enrichment) -> Room1/Room2/GNN/TrustBadge ->
Router -> Stage 3 SLM (Cline-backed) -> per-chat output.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from uspi.common.hashing import entity_hash, new_case_id
from uspi.common.schema import CanonicalEvent, Signal
from uspi.text.enrichment import EntityEnrichment
from uspi.text.gnn_prior import GnnPrior
from uspi.text.lexicon import Lexicon
from uspi.text.room1 import Room1EntityReputation, ReportEvent
from uspi.text.room2 import Room2ChatContext
from uspi.text.router import ContextAssembler, Router
from uspi.text.slm_stage3 import Stage3SLM
from uspi.text.trust_badge import TrustBadgeManager


@dataclass
class TextChatResult:
    case_id: str
    chat_id: str
    ran_slm: bool
    slm_signal: Optional[Signal]
    room1_prior: float
    room2_accumulator: float
    funnel_stage: str
    trust_suspended_reason: Optional[str]
    entity_signals: List[dict]
    t_star_message_index: Optional[int]


class TextPipeline:
    def __init__(
        self,
        lexicon: Optional[Lexicon] = None,
        enrichment: Optional[EntityEnrichment] = None,
        room1: Optional[Room1EntityReputation] = None,
        room2: Optional[Room2ChatContext] = None,
        gnn: Optional[GnnPrior] = None,
        trust_badge: Optional[TrustBadgeManager] = None,
        router: Optional[Router] = None,
        assembler: Optional[ContextAssembler] = None,
        slm: Optional[Stage3SLM] = None,
    ) -> None:
        self.lexicon = lexicon or Lexicon()
        self.enrichment = enrichment or EntityEnrichment()
        self.room1 = room1 or Room1EntityReputation()
        self.room2 = room2 or Room2ChatContext()
        self.gnn = gnn or GnnPrior()
        self.trust_badge = trust_badge or TrustBadgeManager()
        self.router = router or Router()
        self.assembler = assembler or ContextAssembler()
        self.slm = slm or Stage3SLM()
        self._message_history: Dict[str, List[dict]] = {}

    def process_event(self, event: CanonicalEvent, case_id: Optional[str] = None) -> TextChatResult:
        case_id = case_id or new_case_id("text")
        chat_id = event.chat_id
        text = event.text or ""

        lex_result = self.lexicon.score(text)
        category_weights = {
            cat: lex_result.category_weight(cat)
            for cat in {"urgency", "money", "otp", "authority", "off_platform"}
        }

        enrich_results = self.enrichment.find_entities(text)
        entity_signals = [r.__dict__ for r in enrich_results]

        tripwire_reason = self.trust_badge.apply_tripwire(
            chat_id, text, event.extra.get("event_flags", [])
        )

        room2_state = self.room2.ingest_message(chat_id, category_weights, event.ts_utc)

        entity_flags = []
        if any(r.kind == "url" for r in enrich_results):
            entity_flags.append("has_link")
        if category_weights.get("money", 0) > 0:
            entity_flags.append("money_ask")
        if category_weights.get("otp", 0) > 0:
            entity_flags.append("otp_ask")
        if category_weights.get("off_platform", 0) > 0:
            entity_flags.append("platform_shift")
        if tripwire_reason:
            entity_flags.append("tripwire")

        room1_prior_val = 0.0
        for r in enrich_results:
            eh = entity_hash(r.value_hint)
            self.room1.record_report(
                ReportEvent(
                    entity_hash=eh,
                    reporter_hash=entity_hash(chat_id),
                    reporter_trust=1.0,
                    weight=r.risk_score,
                    ts_utc=event.ts_utc,
                    recipient_hash=entity_hash(chat_id),
                )
            )
            room1_prior_val = max(room1_prior_val, self.room1.prior_for(eh, event.ts_utc))

        history = self._message_history.setdefault(chat_id, [])
        history.append({"index": len(history), "text_hash": entity_hash(text)[:12], "ts_utc": event.ts_utc})

        ran_slm = self.router.should_run_slm(chat_id, entity_flags)
        slm_signal: Optional[Signal] = None
        t_star: Optional[int] = None

        if ran_slm:
            context = self.assembler.assemble(
                chat_id=chat_id,
                messages=history,
                event_messages=[m for m in history if m["index"] == 0],
                funnel_state=room2_state.funnel_stage.name,
                room1_prior=room1_prior_val,
                gnn_prior=self.gnn.prior_for(chat_id, {}),
                scam_exemplars=[],
            )
            slm_signal = self.slm.analyse(case_id, context.to_prompt_payload())
            self.router.record_score(chat_id, slm_signal.value)
            t_star = self.slm.localize_t_star(slm_signal.extra.get("per_message_scores", []))

        return TextChatResult(
            case_id=case_id,
            chat_id=chat_id,
            ran_slm=ran_slm,
            slm_signal=slm_signal,
            room1_prior=room1_prior_val,
            room2_accumulator=room2_state.accumulator,
            funnel_stage=room2_state.funnel_stage.name,
            trust_suspended_reason=tripwire_reason,
            entity_signals=entity_signals,
            t_star_message_index=t_star,
        )
