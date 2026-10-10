"""UX wording helpers (architecture section 11.3): warnings describe
behaviour, never accuse a person.
"""
from __future__ import annotations

from typing import List


def build_behavioural_warning(evidence_tags: List[str], tier: str) -> str:
    if not evidence_tags:
        return "No specific risk indicators to describe yet."
    joined = "; ".join(evidence_tags[:3])
    return f"This conversation asked you to: {joined}. Risk tier: {tier}."
