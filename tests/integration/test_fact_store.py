"""Fact store integration tests (docs/09 §4). Require a running Postgres:
``python tools/dev.py up``. Excluded from default CI (`-m "not integration"`).
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
def conn() -> Iterator[psycopg.Connection[dict[str, Any]]]:
    try:
        connection = psycopg.connect(_dsn(), row_factory=dict_row, connect_timeout=3)
    except psycopg.OperationalError as exc:  # pragma: no cover - infra-dependent
        pytest.skip(f"Postgres not available: {exc}")
    yield connection
    connection.close()


@pytest.fixture
def store(
    conn: psycopg.Connection[dict[str, Any]],
) -> Iterator[tuple[ProductRepository, FactRepository, list[str]]]:
    created: list[str] = []
    yield ProductRepository(conn), FactRepository(conn), created
    with conn.transaction(), conn.cursor() as cur:
        for product_id in created:
            cur.execute("DELETE FROM facts WHERE product_id = %s", (product_id,))
            cur.execute("DELETE FROM products WHERE product_id = %s", (product_id,))


def make_fact(product_id: str, value: float, span: str) -> CanonicalFact:
    return CanonicalFact(
        product_id=product_id,
        attribute_key="net_weight",
        ontology_version=1,
        data_type=DataType.QUANTITY,
        canonical_value=value,
        canonical_unit="g",
        original_value=f"{value} g",
        confidence=0.95,
        provenance=Provenance(
            source_type="json_ld",
            source_url="https://example-vendor.com/products/acme-model-x",
            extraction_tier=ExtractionTier.STRUCTURED_DATA,
            extraction_method="jsonld_v1",
            source_span=span,
            raw_artifact_id="s3://raw-artifacts/test/x.html",
            fetched_at=datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
        ),
        valid_from=datetime(2026, 7, 12, 12, 0, tzinfo=UTC),
    )


Store = tuple[ProductRepository, FactRepository, list[str]]


class TestEntityResolution:
    def test_resolve_by_gtin_is_stable(self, store: Store) -> None:
        products, _, created = store
        ref = ProductRef(
            brand="TestBrand",
            model="Model-X",
            gtin="TEST-GTIN-4006381333931",
            source_url="https://example-vendor.com/products/acme-model-x",
        )
        first = products.resolve_or_create(ref)
        created.append(first)
        second = products.resolve_or_create(ref)
        assert first == second

    def test_resolve_by_brand_model_when_no_gtin(self, store: Store) -> None:
        products, _, created = store
        a = products.resolve_or_create(ProductRef(brand="TestBrand", model="NoGtin-1"))
        created.append(a)
        b = products.resolve_or_create(ProductRef(brand="TestBrand", model="nogtin-1"))
        assert a == b  # case-insensitive model match


class TestFactVersioning:
    def test_new_value_supersedes_previous(self, store: Store) -> None:
        products, facts, created = store
        pid = products.resolve_or_create(
            ProductRef(brand="TestBrand", model="Ver-1", gtin="TEST-GTIN-VER1")
        )
        created.append(pid)

        facts.upsert(make_fact(pid, 2300.0, '"weight": "2.3 kg"'))
        facts.upsert(make_fact(pid, 2400.0, '"weight": "2.4 kg"'))

        current = facts.get_effective_fact(pid, "net_weight")
        assert current is not None
        assert current.canonical_value == 2400.0
        # exactly one effective fact remains for the attribute
        effective = [f for f in facts.get_effective_facts(pid) if f.attribute_key == "net_weight"]
        assert len(effective) == 1

    def test_identical_reinsert_is_idempotent(self, store: Store) -> None:
        products, facts, created = store
        pid = products.resolve_or_create(
            ProductRef(brand="TestBrand", model="Idem-1", gtin="TEST-GTIN-IDEM1")
        )
        created.append(pid)

        first_id = facts.upsert(make_fact(pid, 2300.0, '"weight": "2.3 kg"'))
        second_id = facts.upsert(make_fact(pid, 2300.0, '"weight": "2.3 kg"'))
        assert first_id == second_id

    def test_roundtrip_preserves_provenance(self, store: Store) -> None:
        products, facts, created = store
        pid = products.resolve_or_create(
            ProductRef(brand="TestBrand", model="Round-1", gtin="TEST-GTIN-ROUND1")
        )
        created.append(pid)

        facts.upsert(make_fact(pid, 2300.0, '"weight": "2.3 kg"'))
        fetched = facts.get_effective_fact(pid, "net_weight")
        assert fetched is not None
        assert fetched.provenance.extraction_method == "jsonld_v1"
        assert fetched.provenance.fetched_at == datetime(2026, 7, 12, 10, 0, tzinfo=UTC)
        assert fetched.canonical_unit == "g"
