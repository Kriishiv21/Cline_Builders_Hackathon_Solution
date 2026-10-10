"""RAG scam-pattern store (C19, architecture section 6/10.3).

Hand-written patterns file (no live scraping/refresh), used as hints only
(never instruction execution — section 11.1 injection threat model).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from uspi.common.config import CONFIG_DIR


class ScamPatternStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (CONFIG_DIR / "scam_patterns.json")
        with open(self.path, "r", encoding="utf-8") as fh:
            self.patterns: List[dict] = json.load(fh)

    def top_matches(self, transcript_text: str, k: int = 3) -> List[dict]:
        """Simple keyword-overlap retrieval (deterministic, no embeddings
        service dependency) — adequate for a hand-written hint store."""
        text_lower = (transcript_text or "").lower()
        scored = []
        for pattern in self.patterns:
            overlap = sum(1 for kw in pattern.get("keywords", []) if kw in text_lower)
            if overlap > 0:
                scored.append((overlap, pattern))
        scored.sort(key=lambda x: -x[0])
        return [p for _, p in scored[:k]]

    def lookalikes(self) -> List[dict]:
        return [p for p in self.patterns if p.get("is_lookalike")]
