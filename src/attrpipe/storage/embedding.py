"""Embedding contract for the vector index (docs/04 §5).

The embedding model is injected as a Protocol so the storage layer never hard-
depends on a specific model, and tests can supply a deterministic fake (docs/09
§2). ``dim`` must match the ``chunks.embedding`` column (VECTOR(1024)).
"""

from typing import Protocol

EMBEDDING_DIM = 1024


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...
