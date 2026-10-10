"""Salted on-device-style hashing for entities (section 3.1 of the architecture).

`chat_id_hash`, `sender_id_hash`, `entity_hash`, `recording_id` are all
salted hashes so raw phone numbers, UPI ids, domains and file names never
enter logs, contexts, prompts or ledgers.
"""
from __future__ import annotations

import hashlib
import uuid

from uspi.common.config import env


def _salt() -> str:
    salt = env("HASH_SALT")
    if not salt:
        raise RuntimeError(
            "HASH_SALT is not configured; refusing to hash with an empty salt "
            "(see .env.example)."
        )
    return salt


def salted_hash(value: str, *, namespace: str = "") -> str:
    """Deterministic salted hash. Same salt + namespace -> same hash, so the
    same phone number/UPI id/domain resolves to one entity across channels
    (section 3.5, shared entity layer)."""
    h = hashlib.sha256()
    h.update(_salt().encode("utf-8"))
    h.update(b"|")
    h.update(namespace.encode("utf-8"))
    h.update(b"|")
    h.update(value.strip().lower().encode("utf-8"))
    return h.hexdigest()[:32]


def entity_hash(value: str) -> str:
    return salted_hash(value, namespace="entity")


def chat_id_hash(value: str) -> str:
    return salted_hash(value, namespace="chat")


def sender_id_hash(value: str) -> str:
    return salted_hash(value, namespace="sender")


def new_case_id(prefix: str = "case") -> str:
    """Pseudonymous identifier for one analysed unit (chat episode, recording, call)."""
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def new_recording_id() -> str:
    """Pseudonymous recording identifier; never the file name."""
    return f"rec_{uuid.uuid4().hex[:20]}"


def new_segment_id(case_id: str, start_s: float, end_s: float, index: int) -> str:
    """Deterministic, stable transcript-segment id: same (case, window,
    index) always yields the same id, so STT -> refinement -> content-risk
    -> live-analyser -> fusion -> report all reference one identifier for
    one timestamped span, across the recorded-voice and live-call tracks.
    """
    h = hashlib.sha256()
    h.update(case_id.encode("utf-8"))
    h.update(f"|{start_s:.3f}|{end_s:.3f}|{index}".encode("utf-8"))
    return f"seg_{h.hexdigest()[:16]}"
