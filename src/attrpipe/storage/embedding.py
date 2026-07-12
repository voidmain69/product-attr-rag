"""Embedding contract + a dependency-free default (docs/04 §5).

The embedding model is injected as a Protocol so the storage layer never hard-
depends on a specific model, and tests can supply their own. ``dim`` must match
the ``chunks.embedding`` column (VECTOR(1024)).

``HashingEmbedder`` is a real but simple bag-of-words hashing embedder: it needs
no model or network, so hybrid retrieval works out of the box. It is
term-overlap based (closer to lexical than semantic) and is meant to be swapped
for a multilingual neural model when one is wired in.
"""

import hashlib
import math
import re
from typing import Protocol

EMBEDDING_DIM = 1024
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashingEmbedder:
    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.sha1(token.encode()).digest()
            vec[int.from_bytes(digest[:4], "big") % self.dim] += 1.0
        norm = math.sqrt(sum(x * x for x in vec))
        return vec if norm == 0.0 else [x / norm for x in vec]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]
