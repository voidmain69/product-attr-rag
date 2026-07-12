from datetime import UTC, datetime
from pathlib import Path

import pytest

from attrpipe.domain import CandidateFact, RawArtifact
from attrpipe.domain.facts import ExtractionTier
from attrpipe.extraction import ShopifyAdapter
from attrpipe.normalization import Normalizer

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def load(name: str) -> RawArtifact:
    return RawArtifact(
        raw_artifact_id=f"raw/vendor.myshopify.com/{name}",
        url="https://vendor.myshopify.com/products/acme-model-x.json",
        canonical_url="https://vendor.myshopify.com/products/acme-model-x",
        content=(FIXTURES / name).read_text(encoding="utf-8"),
        content_type="application/json",
        fetched_at=datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
        detected_engine="shopify",
    )


@pytest.fixture
def facts() -> dict[str, CandidateFact]:
    artifact = load("shopify__vendor.myshopify.com__acme-model-x.json")
    return {f.raw_attribute: f for f in ShopifyAdapter().extract(artifact)}


class TestShopifyAdapter:
    def test_weight_uses_grams(self, facts: dict[str, CandidateFact]) -> None:
        weight = facts["weight"]
        assert weight.raw_value == "2300"
        assert weight.raw_unit == "g"

    def test_price_extracted(self, facts: dict[str, CandidateFact]) -> None:
        assert facts["price"].raw_value == "199.00"

    def test_single_value_option_becomes_attribute(self, facts: dict[str, CandidateFact]) -> None:
        assert facts["Color"].raw_value == "Midnight Black"

    def test_multi_value_option_skipped(self, facts: dict[str, CandidateFact]) -> None:
        assert "Size" not in facts  # a variant axis, not a product attribute

    def test_detected_ids(self, facts: dict[str, CandidateFact]) -> None:
        weight = facts["weight"]
        assert weight.detected_ids["brand"] == "Acme"
        assert weight.detected_ids["gtin"] == "4006381333931"
        assert weight.detected_ids["sku"] == "AC-MX-001"

    def test_tier2_provenance(self, facts: dict[str, CandidateFact]) -> None:
        weight = facts["weight"]
        assert weight.provenance.extraction_tier == ExtractionTier.CMS_ADAPTER
        assert weight.provenance.extraction_method == "shopify_json_v1"
        assert weight.confidence == pytest.approx(0.9)

    def test_grounding_invariant(self, facts: dict[str, CandidateFact]) -> None:
        artifact = load("shopify__vendor.myshopify.com__acme-model-x.json")
        for fact in facts.values():
            assert fact.raw_value in artifact.content


class TestNotApplicable:
    def test_non_shopify_json_returns_empty(self) -> None:
        artifact = RawArtifact(
            raw_artifact_id="raw/x",
            url="https://x/y",
            content='{"something": "else"}',
            content_type="application/json",
            fetched_at=datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
        )
        assert ShopifyAdapter().extract(artifact) == []

    def test_html_returns_empty(self) -> None:
        artifact = RawArtifact(
            raw_artifact_id="raw/x",
            url="https://x/y",
            content="<html><body>not json</body></html>",
            fetched_at=datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
        )
        assert ShopifyAdapter().extract(artifact) == []


class TestFeedsNormalization:
    def test_to_canonical(self, facts: dict[str, CandidateFact]) -> None:
        normalizer = Normalizer()
        now = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)
        canonical = {
            f.attribute_key: f
            for c in facts.values()
            if (f := normalizer.normalize(c, "prd_1", now)) is not None
        }
        assert canonical["net_weight"].canonical_value == 2300.0
        assert canonical["net_weight"].canonical_unit == "g"
        assert canonical["color"].canonical_value == "Midnight Black"
