from datetime import UTC, datetime

import pytest

from attrpipe.domain import CanonicalFact, Provenance
from attrpipe.domain.facts import DataType, ExtractionTier
from attrpipe.rag import AnswerService, AttributeQueryParser, Route


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
            fetched_at=datetime(2026, 7, 10, 12, 0, tzinfo=UTC),
        ),
        valid_from=datetime(2026, 7, 12, 12, 0, tzinfo=UTC),
    )


WEIGHT = make_fact("net_weight", 2300.0, "g", "2.3 kg")


class FakeResolver:
    def resolve(
        self,
        *,
        gtin: str | None = None,
        mpn: str | None = None,
        brand: str | None = None,
        model: str | None = None,
    ) -> str | None:
        if gtin == "4006381333931" or (brand == "Acme" and model == "Model X"):
            return "prd_1"
        return None


class FakeFacts:
    def get_effective_fact(self, product_id: str, attribute_key: str) -> CanonicalFact | None:
        if product_id == "prd_1" and attribute_key == "net_weight":
            return WEIGHT
        return None


class TestAttributeQueryParser:
    def setup_method(self) -> None:
        self.parser = AttributeQueryParser()

    @pytest.mark.parametrize(
        ("question", "key"),
        [
            ("What is the net weight of this model?", "net_weight"),
            ("яка вага навушників?", "net_weight"),
            ("which IP rating does it have?", "ip_rating"),
            ("tell me the battery life", "battery_life"),
            ("what colour is it?", "color"),
        ],
    )
    def test_extracts_attribute(self, question: str, key: str) -> None:
        assert self.parser.parse(question) == key

    def test_longest_phrase_wins(self) -> None:
        # "battery life" must not be shadowed by a shorter "battery" synonym
        assert self.parser.parse("how long is the battery life?") == "battery_life"

    def test_no_attribute_returns_none(self) -> None:
        assert self.parser.parse("is it a good product overall?") is None


class TestAnswerService:
    def setup_method(self) -> None:
        self.service = AnswerService(FakeResolver(), FakeFacts())

    def test_exact_lookup_with_citation(self) -> None:
        result = self.service.answer("what is the weight?", brand="Acme", model="Model X")
        assert result.found is True
        assert result.route == Route.EXACT_LOOKUP
        assert result.canonical_value == 2300.0
        assert result.canonical_unit == "g"
        assert result.citation is not None
        assert result.citation.source_url.startswith("https://example-vendor.com")
        assert "2300.0 g" in result.answer
        assert "as of 2026-07-10" in result.answer

    def test_resolve_by_gtin(self) -> None:
        result = self.service.answer("weight?", gtin="4006381333931")
        assert result.product_id == "prd_1"
        assert result.found is True

    def test_unknown_attribute_is_ambiguous(self) -> None:
        result = self.service.answer("is it nice?", brand="Acme", model="Model X")
        assert result.route == Route.AMBIGUOUS
        assert result.found is False

    def test_unresolved_product_is_refused(self) -> None:
        result = self.service.answer("what is the weight?", brand="Nobody", model="Nothing")
        assert result.route == Route.REFUSED
        assert result.found is False

    def test_missing_fact_is_honest_unknown(self) -> None:
        # Product resolves, attribute parses, but no such fact -> no fabrication.
        result = self.service.answer("which IP rating?", brand="Acme", model="Model X")
        assert result.route == Route.REFUSED
        assert result.found is False
        assert "No data" in result.answer
