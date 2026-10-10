"""Stage 1 normalizer + lexicon (architecture section 4.2).

Deterministic, rule-based category weighting with negation awareness.
No model training involved, so this stays plain Python (no Cline call).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List

from uspi.common.config import load_yaml

_LEET_MAP = str.maketrans({
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s",
})

_ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\ufeff]")


def normalize_text(text: str) -> str:
    """Leetspeak, homoglyph (NFKC fold), zero-width stripping."""
    if not text:
        return ""
    text = _ZERO_WIDTH.sub("", text)
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    text = text.translate(_LEET_MAP)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@dataclass
class LexiconHit:
    category: str
    weight: float
    phrase: str


@dataclass
class LexiconResult:
    hits: List[LexiconHit] = field(default_factory=list)
    negated_categories: List[str] = field(default_factory=list)

    def category_weight(self, category: str) -> float:
        if category in self.negated_categories:
            return 0.0
        return sum(h.weight for h in self.hits if h.category == category)

    def total_weight(self) -> float:
        return sum(
            h.weight for h in self.hits if h.category not in self.negated_categories
        )


class Lexicon:
    """Category weights for urgency, money, OTP, authority, off-platform.
    Negation-aware: 'never share your OTP' suppresses the hit."""

    def __init__(self, config_path: str = "text_lexicon.yaml") -> None:
        cfg = load_yaml(config_path)
        self.categories: Dict[str, List[dict]] = cfg.get("categories", {})
        self.negation_markers: List[str] = cfg.get("negation_markers", [])
        self.negation_window = cfg.get("negation_window_tokens", 4)
        self.config_version = cfg.get("_config_version", "unversioned")

    def score(self, raw_text: str) -> LexiconResult:
        text = normalize_text(raw_text)
        tokens = text.split()
        result = LexiconResult()
        negated_categories: set[str] = set()

        for category, entries in self.categories.items():
            for entry in entries:
                phrase = entry["phrase"]
                weight = float(entry["weight"])
                idx = text.find(phrase)
                if idx == -1:
                    continue
                result.hits.append(LexiconHit(category=category, weight=weight, phrase=phrase))
                phrase_token_idx = len(text[:idx].split())
                window_start = max(0, phrase_token_idx - self.negation_window)
                window_tokens = tokens[window_start:phrase_token_idx]
                if any(marker in window_tokens for marker in self.negation_markers):
                    negated_categories.add(category)

        result.negated_categories = list(negated_categories)
        return result
