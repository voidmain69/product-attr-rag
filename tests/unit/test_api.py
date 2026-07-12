from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from attrpipe.api.app import create_app
from attrpipe.api.deps import (
    get_answer_service,
    get_fact_repository,
    get_product_repository,
)
from attrpipe.domain import CanonicalFact, Provenance
from attrpipe.domain.facts import DataType, ExtractionTier
from attrpipe.rag import AnswerService
from attrpipe.storage import ProductRecord


def make_fact(attribute_key: str, value: object, unit: str | None, original: str) -> CanonicalFact:
    return CanonicalFact(
        product_id="prd_1",
        attribute_key=attribute_key,
        ontology_version=1,
        data_type=DataType.QUANTITY if unit else DataType.TEXT,
        canonical_value=value,
        canonical_unit=unit,
        original_value=original,
        confidence=0.95,
        provenance=Provenance(
            source_type="json_ld",
            source_url="https://example-vendor.com/products/acme-model-x",
            extraction_tier=ExtractionTier.STRUCTURED_DATA,
            extraction_method="jsonld_v1",
            source_span=f'"{attribute_key}": "{original}"',
            raw_artifact_id="s3://raw-artifacts/test/x.html",
            fetched_at=datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
        ),
        valid_from=datetime(2026, 7, 12, 12, 0, tzinfo=UTC),
    )


FACTS = [
    make_fact("net_weight", 2300.0, "g", "2.3 kg"),
    make_fact("ip_rating", "IP67", None, "IP67"),
]


class FakeFactRepository:
    def get_effective_facts(self, product_id: str) -> list[CanonicalFact]:
        return FACTS if product_id == "prd_1" else []

    def get_effective_fact(self, product_id: str, attribute_key: str) -> CanonicalFact | None:
        if product_id != "prd_1":
            return None
        return next((f for f in FACTS if f.attribute_key == attribute_key), None)


class FakeProductRepository:
    def get(self, product_id: str) -> ProductRecord | None:
        if product_id != "prd_1":
            return None
        return ProductRecord(
            product_id="prd_1",
            brand="Acme",
            model="Model X",
            category_path=["electronics", "audio", "headphones"],
            gtin="4006381333931",
            mpn="MX-001",
            canonical_title="Acme Model X",
            source_urls=["https://example-vendor.com/products/acme-model-x"],
        )


class FakeResolver:
    def resolve(
        self,
        *,
        gtin: str | None = None,
        mpn: str | None = None,
        brand: str | None = None,
        model: str | None = None,
    ) -> str | None:
        return "prd_1" if (brand == "Acme" and model == "Model X") else None


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_fact_repository] = FakeFactRepository
    app.dependency_overrides[get_product_repository] = FakeProductRepository
    app.dependency_overrides[get_answer_service] = lambda: AnswerService(
        FakeResolver(), FakeFactRepository()
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestOps:
    def test_healthz(self, client: TestClient) -> None:
        assert client.get("/healthz").json() == {"status": "ok"}

    def test_metrics_exposed(self, client: TestClient) -> None:
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "attrpipe_rag_route_total" in resp.text


class TestAttributes:
    def test_lists_ontology(self, client: TestClient) -> None:
        keys = {a["attribute_key"] for a in client.get("/v1/attributes").json()}
        assert {"net_weight", "ip_rating", "battery_life"} <= keys


class TestExactLookup:
    def test_get_product(self, client: TestClient) -> None:
        body = client.get("/v1/products/prd_1").json()
        assert body["brand"] == "Acme"
        assert body["gtin"] == "4006381333931"

    def test_unknown_product_404(self, client: TestClient) -> None:
        assert client.get("/v1/products/nope").status_code == 404

    def test_all_facts(self, client: TestClient) -> None:
        facts = client.get("/v1/products/prd_1/facts").json()
        by_key = {f["attribute_key"]: f for f in facts}
        assert by_key["net_weight"]["canonical_value"] == 2300.0
        assert by_key["net_weight"]["canonical_unit"] == "g"

    def test_single_fact_carries_citation(self, client: TestClient) -> None:
        fact = client.get("/v1/products/prd_1/facts/net_weight").json()
        assert fact["canonical_value"] == 2300.0
        assert fact["source_url"].startswith("https://example-vendor.com")
        assert fact["fetched_at"].startswith("2026-07-12")

    def test_missing_fact_is_honest_404(self, client: TestClient) -> None:
        # No fabricated value when the fact is absent (CLAUDE.md §2.6).
        assert client.get("/v1/products/prd_1/facts/waterproof").status_code == 404


class TestAnswer:
    def test_exact_lookup_answer(self, client: TestClient) -> None:
        body = client.post(
            "/v1/answer",
            json={"question": "what is the weight?", "brand": "Acme", "model": "Model X"},
        ).json()
        assert body["found"] is True
        assert body["route"] == "exact_lookup"
        assert body["canonical_value"] == 2300.0
        assert body["citation"]["source_url"].startswith("https://example-vendor.com")

    def test_ambiguous_question(self, client: TestClient) -> None:
        body = client.post("/v1/answer", json={"question": "is it good?"}).json()
        assert body["route"] == "ambiguous"
        assert body["found"] is False

    def test_unknown_product_refused(self, client: TestClient) -> None:
        body = client.post(
            "/v1/answer",
            json={"question": "what is the weight?", "brand": "Nobody", "model": "X"},
        ).json()
        assert body["route"] == "refused"
        assert body["found"] is False
