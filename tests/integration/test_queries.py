"""filter / compare integration tests (docs/09 §4). Require Postgres:
``python tools/dev.py up``. Excluded from default CI.
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import psycopg
import pytest
from psycopg.rows import dict_row

from attrpipe.domain import CanonicalFact, Provenance
from attrpipe.domain.facts import DataType, ExtractionTier
from attrpipe.storage import Constraint, FactRepository, ProductRef, ProductRepository

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
    created: list[str] = []
    yield ProductRepository(conn), FactRepository(conn), created
    with conn.transaction(), conn.cursor() as cur:
        for product_id in created:
            cur.execute("DELETE FROM facts WHERE product_id = %s", (product_id,))
            cur.execute("DELETE FROM products WHERE product_id = %s", (product_id,))
    conn.close()


def fact(product_id: str, key: str, value: object, unit: str | None) -> CanonicalFact:
    return CanonicalFact(
        product_id=product_id,
        attribute_key=key,
        ontology_version=1,
        data_type=DataType.QUANTITY if unit else DataType.TEXT,
        canonical_value=value,
        canonical_unit=unit,
        original_value=f"{value}{unit or ''}",
        confidence=0.95,
        provenance=Provenance(
            source_type="json_ld",
            source_url="https://example-vendor.com/x",
            extraction_tier=ExtractionTier.STRUCTURED_DATA,
            extraction_method="jsonld_v1",
            source_span="span",
            raw_artifact_id="s3://raw/x",
            fetched_at=datetime(2026, 7, 10, 12, 0, tzinfo=UTC),
        ),
        valid_from=datetime(2026, 7, 12, 12, 0, tzinfo=UTC),
    )


def _seed(
    products: ProductRepository, facts: FactRepository, created: list[str]
) -> tuple[str, str]:
    light = products.resolve_or_create(ProductRef(brand="QBrand", model="Light", gtin="Q-LIGHT"))
    heavy = products.resolve_or_create(ProductRef(brand="QBrand", model="Heavy", gtin="Q-HEAVY"))
    created.extend([light, heavy])
    facts.upsert(fact(light, "net_weight", 250.0, "g"))
    facts.upsert(fact(light, "ip_rating", "IP67", None))
    facts.upsert(fact(heavy, "net_weight", 900.0, "g"))
    facts.upsert(fact(heavy, "ip_rating", "IP54", None))
    return light, heavy


class TestFilter:
    def test_numeric_filter(
        self, repos: tuple[ProductRepository, FactRepository, list[str]]
    ) -> None:
        products, facts, created = repos
        light, heavy = _seed(products, facts, created)
        result = facts.filter_products([Constraint(attribute_key="net_weight", op="lt", value=300)])
        assert light in result
        assert heavy not in result

    def test_combined_constraints(
        self, repos: tuple[ProductRepository, FactRepository, list[str]]
    ) -> None:
        products, facts, created = repos
        light, heavy = _seed(products, facts, created)
        result = facts.filter_products(
            [
                Constraint(attribute_key="ip_rating", op="eq", value="IP67"),
                Constraint(attribute_key="net_weight", op="lt", value=300),
            ]
        )
        # membership, not exact equality — the filter scans the whole store, which
        # may hold unrelated products from other work.
        assert light in result
        assert heavy not in result

    def test_no_match(self, repos: tuple[ProductRepository, FactRepository, list[str]]) -> None:
        products, facts, created = repos
        _seed(products, facts, created)
        assert (
            facts.filter_products([Constraint(attribute_key="net_weight", op="lt", value=1)]) == []
        )


class TestCompare:
    def test_compare_returns_effective_facts(
        self, repos: tuple[ProductRepository, FactRepository, list[str]]
    ) -> None:
        products, facts, created = repos
        light, heavy = _seed(products, facts, created)
        result = facts.compare([light, heavy], ["net_weight"])
        by_product = {f.product_id: f.canonical_value for f in result}
        assert by_product[light] == 250.0
        assert by_product[heavy] == 900.0
