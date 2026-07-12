"""Chunk store + dense retrieval integration (docs/09 §4). Requires Postgres+pgvector:
``python tools/dev.py up``. Excluded from default CI.
"""

import os
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from psycopg.rows import dict_row

from attrpipe.storage import Chunk, ChunkRepository, HashingEmbedder

pytestmark = pytest.mark.integration


def _dsn() -> str:
    password = os.environ.get("POSTGRES_PASSWORD", "attrpipe-local")
    return f"postgresql://attrpipe:{password}@localhost:5432/attrpipe"


def make_chunk(product_id: str, brand: str, body: str) -> Chunk:
    return Chunk(
        chunk_id=f"chk_{product_id}",
        product_id=product_id,
        kind="fact",
        body=body,
        attribute_keys=["net_weight", "ip_rating"],
        brand=brand,
        category_path=["electronics", "audio", "headphones"],
        source_url="https://v/x",
        fetched_at=None,
    )


def _seed_product(conn: psycopg.Connection[dict[str, Any]], product_id: str, brand: str) -> None:
    # chunks.product_id has a FK to products — the product must exist first.
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "INSERT INTO products (product_id, brand, model) VALUES (%s,%s,%s)"
            " ON CONFLICT (product_id) DO NOTHING",
            (product_id, brand, "M"),
        )


@pytest.fixture
def repo() -> Iterator[tuple[ChunkRepository, psycopg.Connection[dict[str, Any]], list[str]]]:
    try:
        conn = psycopg.connect(_dsn(), row_factory=dict_row, connect_timeout=3)
    except psycopg.OperationalError as exc:  # pragma: no cover
        pytest.skip(f"Postgres not available: {exc}")
    created: list[str] = []
    yield ChunkRepository(conn, HashingEmbedder()), conn, created
    with conn.transaction(), conn.cursor() as cur:
        for product_id in created:
            cur.execute("DELETE FROM chunks WHERE product_id = %s", (product_id,))
            cur.execute("DELETE FROM products WHERE product_id = %s", (product_id,))
    conn.close()


class TestChunkStore:
    def test_index_and_dense_search_ranks_relevant_first(
        self, repo: tuple[ChunkRepository, psycopg.Connection[dict[str, Any]], list[str]]
    ) -> None:
        chunks, conn, created = repo
        created.extend(["cs_buds", "cs_speaker"])
        _seed_product(conn, "cs_buds", "CsRank")
        _seed_product(conn, "cs_speaker", "CsRank")
        chunks.index(
            make_chunk(
                "cs_buds",
                "CsRank",
                "[Brand: CsRank] [Model: Buds] wireless earbuds waterproof ip67 rating",
            )
        )
        chunks.index(
            make_chunk(
                "cs_speaker",
                "CsRank",
                "[Brand: CsRank] [Model: Speaker] bluetooth speaker loud bass heavy",
            )
        )

        # brand filter isolates this test's two chunks from any others in the table
        hits = chunks.search("is it waterproof ip67", brand="CsRank", limit=2)
        assert hits[0].product_id == "cs_buds"  # shares waterproof/ip67 tokens

    def test_reindex_replaces_previous_chunk(
        self, repo: tuple[ChunkRepository, psycopg.Connection[dict[str, Any]], list[str]]
    ) -> None:
        chunks, conn, created = repo
        created.append("cs_reindex")
        _seed_product(conn, "cs_reindex", "AcmeCS")
        chunks.index(make_chunk("cs_reindex", "AcmeCS", "old body v1"))
        chunks.index(make_chunk("cs_reindex", "AcmeCS", "new body v2"))
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM chunks WHERE product_id = %s", ("cs_reindex",))
            row = cur.fetchone()
            assert row is not None
            assert row["n"] == 1  # regenerated, not duplicated

    def test_brand_filter(
        self, repo: tuple[ChunkRepository, psycopg.Connection[dict[str, Any]], list[str]]
    ) -> None:
        chunks, conn, created = repo
        created.extend(["cs_a", "cs_b"])
        _seed_product(conn, "cs_a", "BrandA")
        _seed_product(conn, "cs_b", "BrandB")
        chunks.index(make_chunk("cs_a", "BrandA", "waterproof ip67 earbuds"))
        chunks.index(make_chunk("cs_b", "BrandB", "waterproof ip67 earbuds"))
        hits = chunks.search("waterproof ip67", brand="BrandB", limit=5)
        assert {h.product_id for h in hits} == {"cs_b"}
