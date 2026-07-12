"""Chunk store + dense retrieval over pgvector (docs/04 §5).

Persists self-contained chunks with their embeddings and serves dense
(cosine) search narrowed by metadata filters (brand/category) applied *before*
ranking (docs/04 §5). Chunks are derived data: a product's chunk is regenerated
(delete + insert) whenever its facts change, so stale vectors never linger
(docs/04 §4.3).
"""

from datetime import datetime
from typing import Any

import psycopg
from pydantic import BaseModel

from attrpipe.storage.chunk import Chunk
from attrpipe.storage.embedding import Embedder


class ChunkHit(BaseModel):
    chunk_id: str
    product_id: str
    body: str
    brand: str | None
    attribute_keys: list[str]
    source_url: str | None
    fetched_at: datetime | None
    distance: float


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


class ChunkRepository:
    def __init__(self, conn: psycopg.Connection[dict[str, Any]], embedder: Embedder) -> None:
        self._conn = conn
        self._embedder = embedder

    def index(self, chunk: Chunk) -> None:
        """Embed and store ``chunk``, replacing any existing chunk for its product+kind."""
        embedding = self._embedder.embed([chunk.body])[0]
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chunks WHERE product_id = %s AND kind = %s",
                (chunk.product_id, chunk.kind),
            )
            cur.execute(
                "INSERT INTO chunks (chunk_id, product_id, kind, body, attribute_keys,"
                " brand, category_path, source_url, fetched_at, embedding)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)",
                (
                    chunk.chunk_id,
                    chunk.product_id,
                    chunk.kind,
                    chunk.body,
                    chunk.attribute_keys,
                    chunk.brand,
                    chunk.category_path,
                    chunk.source_url,
                    chunk.fetched_at,
                    _vector_literal(embedding),
                ),
            )

    def search(
        self,
        query: str,
        *,
        brand: str | None = None,
        category: str | None = None,
        limit: int = 5,
    ) -> list[ChunkHit]:
        query_vector = _vector_literal(self._embedder.embed([query])[0])
        # Placeholder order must match the SQL text: SELECT distance, WHERE filters, LIMIT.
        params: list[Any] = [query_vector]
        clauses: list[str] = ["stale = FALSE"]
        if brand is not None:
            clauses.append("brand = %s")
            params.append(brand)
        if category is not None:
            clauses.append("%s = ANY(category_path)")
            params.append(category)
        params.append(limit)
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT chunk_id, product_id, body, brand, attribute_keys, source_url,"
                " fetched_at, embedding <=> %s::vector AS distance FROM chunks"
                f" WHERE {' AND '.join(clauses)} ORDER BY distance LIMIT %s",
                params,
            )
            return [ChunkHit.model_validate(row) for row in cur.fetchall()]
