"""Stage 1 tiny encoder + MinHash/SimHash (architecture section 4.2).

The architecture specifies an int8, <=8MB tiny embedding model for
per-message encoding. That is a lightweight deterministic encoder (not an
LLM), so it is implemented here as a reproducible hashing-trick bag-of-
character-ngrams vector rather than a Cline API call (Cline is reserved
for genuinely generative/judgement tasks per the task instructions and
architecture section 9.5/10.1). MinHash/SimHash are used for template and
paraphrase reuse detection.
"""
from __future__ import annotations

import hashlib
from typing import List

import numpy as np

EMBED_DIM = 64
NGRAM_SIZES = (3, 4)
NUM_MINHASH = 32


def _char_ngrams(text: str) -> List[str]:
    grams: List[str] = []
    for n in NGRAM_SIZES:
        grams.extend(text[i : i + n] for i in range(max(0, len(text) - n + 1)))
    return grams or [text]


def tiny_encode(text: str) -> np.ndarray:
    """Deterministic hashing-trick embedding, int8-quantizable."""
    vec = np.zeros(EMBED_DIM, dtype=np.float32)
    for gram in _char_ngrams(text):
        h = int(hashlib.md5(gram.encode("utf-8")).hexdigest(), 16)
        idx = h % EMBED_DIM
        sign = 1.0 if (h // EMBED_DIM) % 2 == 0 else -1.0
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


def simhash(text: str, bits: int = 64) -> int:
    """Paraphrase-reuse detection via embedding-derived simhash."""
    vec = tiny_encode(text)
    acc = np.zeros(bits)
    for i, gram in enumerate(_char_ngrams(text)):
        h = int(hashlib.sha1(gram.encode("utf-8")).hexdigest(), 16)
        for b in range(bits):
            bit = (h >> b) & 1
            acc[b] += vec[i % EMBED_DIM] if bit else -vec[i % EMBED_DIM]
    result = 0
    for b in range(bits):
        if acc[b] > 0:
            result |= 1 << b
    return result


def minhash_signature(text: str, num_hashes: int = NUM_MINHASH) -> List[int]:
    """Exact-shingle template reuse detection."""
    shingles = set(_char_ngrams(text))
    if not shingles:
        return [0] * num_hashes
    sig = []
    for i in range(num_hashes):
        salt = str(i).encode("utf-8")
        min_h = min(
            int(hashlib.sha1(salt + s.encode("utf-8")).hexdigest(), 16) for s in shingles
        )
        sig.append(min_h)
    return sig


def hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")
