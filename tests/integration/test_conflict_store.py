"""Conflict resolution in the fact store (docs/03 §5, docs/09 §4).
Requires Postgres: ``python tools/dev.py up``. Excluded from default CI.
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import psycopg
import pytest
from psycopg.rows import dict_row

from attrpipe.domain import CanonicalFact, Provenance
from attrpipe.domain.facts import DataType, ExtractionTier
from attrpipe.storage import FactRepository, ProductRef, ProductRepository

pytestmark = pytest.mark.integration


def _dsn() -> str:
    password = os.environ.get("POSTGRES_PASSWORD", "attrpipe-local")
    return f"postgresql://attrpipe:{password}@localhost:5432/attrpipe"


@pytest.fixture
def repos() -> Iterator[tuple[ProductRepository, FactRepository, list[str]]]:
    try:
        conn = psycopg.connect(_dsn(), row_factory=dict_row, connect_timeout=3)
    except psycopg.OperationalError as exc:  # pragma: no cover
        pytest.skip(f"Postgres not available: {exc}")
    # Clear this file's fixed GTINs up front so a prior run's leftovers can't be
    # re-resolved and inflate fact counts (resolve_or_create matches by GTIN).
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "DELETE FROM facts WHERE product_id IN"
            " (SELECT product_id FROM products WHERE gtin = ANY(%s))",
            (["C-AUTH", "C-DISP", "C-REVAL"],),
        )
        cur.execute("DELETE FROM products WHERE gtin = ANY(%s)", (["C-AUTH", "C-DISP", "C-REVAL"],))
    created: list[str] = []
    yield ProductRepository(conn), FactRepository(conn), created
    with conn.transaction(), conn.cursor() as cur:
        for product_id in created:
            cur.execute("DELETE FROM facts WHERE product_id = %s", (product_id,))
            cur.execute("DELETE FROM products WHERE product_id = %s", (product_id,))
    conn.close()


def fact(
    product_id: str,
    value: float,
    *,
    source_type: str,
    source_url: str,
    tier: ExtractionTier,
    fetched_at: datetime,
) -> CanonicalFact:
    return CanonicalFact(
        product_id=product_id,
        attribute_key="net_weight",
        ontology_version=1,
        data_type=DataType.QUANTITY,
        canonical_value=value,
        canonical_unit="g",
        original_value=f"{value} g",
        confidence=0.9,
        provenance=Provenance(
            source_type=source_type,
            source_url=source_url,
            extraction_tier=tier,
            extraction_method="m",
            source_span="span",
            raw_artifact_id=f"s3://raw/{source_url}",
            fetched_at=fetched_at,
        ),
        valid_from=fetched_at,
    )


def _count_rows(repos_conn: psycopg.Connection[dict[str, Any]], product_id: str) -> int:
    with repos_conn.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM facts WHERE product_id = %s", (product_id,))
        row = cur.fetchone()
        return int(row["n"]) if row else 0


T0 = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
T1 = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


class TestConflictInStore:
    def test_higher_authority_stays_effective(
        self, repos: tuple[ProductRepository, FactRepository, list[str]]
    ) -> None:
        products, facts, created = repos
        pid = products.resolve_or_create(ProductRef(brand="C", model="Auth", gtin="C-AUTH"))
        created.append(pid)

        # DOM first, then a structured source with a different value
        facts.upsert(
            fact(
                pid,
                2400,
                source_type="dom",
                source_url="u_dom",
                tier=ExtractionTier.DOM_HEURISTICS,
                fetched_at=T0,
            )
        )
        facts.upsert(
            fact(
                pid,
                2300,
                source_type="json_ld",
                source_url="u_ld",
                tier=ExtractionTier.STRUCTURED_DATA,
                fetched_at=T0,
            )
        )

        effective = facts.get_effective_fact(pid, "net_weight")
        assert effective is not None
        assert effective.canonical_value == 2300  # structured wins over DOM
        assert effective.disputed is False  # different authority -> not disputed

    def test_equal_authority_conflict_is_disputed_and_both_kept(
        self, repos: tuple[ProductRepository, FactRepository, list[str]]
    ) -> None:
        products, facts, created = repos
        pid = products.resolve_or_create(ProductRef(brand="C", model="Disp", gtin="C-DISP"))
        created.append(pid)

        facts.upsert(
            fact(
                pid,
                2300,
                source_type="json_ld",
                source_url="u_a",
                tier=ExtractionTier.STRUCTURED_DATA,
                fetched_at=T0,
            )
        )
        facts.upsert(
            fact(
                pid,
                2400,
                source_type="json_ld",
                source_url="u_b",
                tier=ExtractionTier.STRUCTURED_DATA,
                fetched_at=T1,
            )
        )

        effective = facts.get_effective_fact(pid, "net_weight")
        assert effective is not None
        assert effective.canonical_value == 2400  # newer wins the equal-authority tie
        assert effective.disputed is True
        # both competing rows retained (provenance preserved), one effective
        with psycopg.connect(_dsn(), row_factory=dict_row) as conn:
            assert _count_rows(conn, pid) == 2

    def test_same_source_revalidation_supersedes(
        self, repos: tuple[ProductRepository, FactRepository, list[str]]
    ) -> None:
        products, facts, created = repos
        pid = products.resolve_or_create(ProductRef(brand="C", model="Reval", gtin="C-REVAL"))
        created.append(pid)

        facts.upsert(
            fact(
                pid,
                2300,
                source_type="json_ld",
                source_url="u_same",
                tier=ExtractionTier.STRUCTURED_DATA,
                fetched_at=T0,
            )
        )
        facts.upsert(
            fact(
                pid,
                2350,
                source_type="json_ld",
                source_url="u_same",
                tier=ExtractionTier.STRUCTURED_DATA,
                fetched_at=T1,
            )
        )

        effective = facts.get_effective_fact(pid, "net_weight")
        assert effective is not None
        assert effective.canonical_value == 2350
        # exactly one effective remains for the attribute
        effective_all = [
            f for f in facts.get_effective_facts(pid) if f.attribute_key == "net_weight"
        ]
        assert len(effective_all) == 1
