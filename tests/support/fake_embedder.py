"""Deterministic hashing embedder for tests — no model, no network (docs/09 §2).

Bag-of-words hashed into a fixed-dim L2-normalized vector: texts sharing tokens
get similar vectors, which is enough to exercise dense retrieval ranking
deterministically.
"""

import hashlib
import math
import re

from attrpipe.storage import EMBEDDING_DIM

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class HashingEmbedder:
    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.sha1(token.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self.dim
            vec[index] += 1.0
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0.0:
            return vec
        return [x / norm for x in vec]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]
