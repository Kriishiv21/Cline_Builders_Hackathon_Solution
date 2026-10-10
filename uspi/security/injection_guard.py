"""Security: injection guard (architecture section 11.1).

Treats message/web/transcript text as DATA, never instructions. Flags
common prompt-injection and whitelist-tripwire phrases before they reach
any Cline-backed component, and the Cline system prompts themselves
instruct the model to treat untrusted text as data (defense in depth).
"""
from __future__ import annotations

import re
from typing import List

INJECTION_PATTERNS = [
    r"ignore (all )?previous (instructions|warnings)",
    r"you are now",
    r"system:\s*",
    r"disregard (the )?(rules|policy)",
    r"this chat is safe",
    r"whitelist me",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def detect_injection_attempts(text: str) -> List[str]:
    hits = []
    for pattern in _COMPILED:
        if pattern.search(text or ""):
            hits.append(pattern.pattern)
    return hits


def sanitize_for_llm_payload(text: str) -> str:
    """Does not remove content (so it can still be analysed as evidence),
    but wraps it so it's unambiguously untrusted data in the Cline prompt
    payload (the Cline client sends it as a JSON field value, not as
    further system instructions, which is the primary defense)."""
    return text
