from datetime import UTC, datetime
from pathlib import Path

import pytest

from attrpipe.domain import RawArtifact
from attrpipe.domain.facts import ExtractionTier
from attrpipe.extraction import StructuredDataExtractor

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def load_artifact(name: str) -> RawArtifact:
    path = FIXTURES / name
    return RawArtifact(
        raw_artifact_id=f"s3://raw-artifacts/test/{name}",
        url="https://example-vendor.com/products/acme-model-x",
        canonical_url="https://example-vendor.com/products/acme-model-x",
        content=path.read_text(encoding="utf-8"),
        fetched_at=datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
        detected_engine="custom",
    )


@pytest.fixture
def facts() -> dict[str, object]:
    artifact = load_artifact("jsonld__example-vendor.com__acme-model-x.html")
    extracted = StructuredDataExtractor().extract(artifact)
    return {f.raw_attribute: f for f in extracted}


class TestStructuredExtractor:
    def test_extracts_scalar_and_quantity_specs(self, facts: dict[str, object]) -> None:
        assert set(facts) >= {
            "color",
            "material",
            "weight",
            "IP rating",
            "Battery life",
            "Bluetooth",
            "price",
        }

    def test_quantity_carries_unit(self, facts: dict[str, object]) -> None:
        weight = facts["weight"]
        assert weight.raw_value == "2.3"  # type: ignore[attr-defined]
        assert weight.raw_unit == "kg"  # type: ignore[attr-defined]

    def test_additional_property_with_unit(self, facts: dict[str, object]) -> None:
        battery = facts["Battery life"]
        assert battery.raw_value == "14"  # type: ignore[attr-defined]
        assert battery.raw_unit == "h"  # type: ignore[attr-defined]

    def test_price_uses_currency_as_unit(self, facts: dict[str, object]) -> None:
        price = facts["price"]
        assert price.raw_value == "199.00"  # type: ignore[attr-defined]
        assert price.raw_unit == "EUR"  # type: ignore[attr-defined]

    def test_provenance_is_tier1_structured(self, facts: dict[str, object]) -> None:
        ip = facts["IP rating"]
        assert ip.provenance.extraction_tier == ExtractionTier.STRUCTURED_DATA  # type: ignore[attr-defined]
        assert ip.provenance.extraction_method == "jsonld_v1"  # type: ignore[attr-defined]
        assert ip.confidence == pytest.approx(0.95)  # type: ignore[attr-defined]

    def test_detected_ids_carried(self, facts: dict[str, object]) -> None:
        weight = facts["weight"]
        assert weight.detected_ids["gtin"] == "4006381333931"  # type: ignore[attr-defined]
        assert weight.detected_ids["mpn"] == "MX-001"  # type: ignore[attr-defined]
        assert weight.detected_ids["brand"] == "Acme"  # type: ignore[attr-defined]

    def test_grounding_invariant_value_present_in_source(self, facts: dict[str, object]) -> None:
        # Anti-hallucination (docs/02 §5.3): every extracted value must actually
        # appear in the raw artifact it was taken from.
        artifact = load_artifact("jsonld__example-vendor.com__acme-model-x.html")
        for fact in facts.values():
            assert fact.raw_value in artifact.content  # type: ignore[attr-defined]


class TestExtractorEdgeCases:
    def test_no_jsonld_returns_empty(self) -> None:
        artifact = RawArtifact(
            raw_artifact_id="s3://raw-artifacts/test/plain.html",
            url="https://example-vendor.com/x",
            content="<html><body><p>no structured data here</p></body></html>",
            fetched_at=datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
        )
        assert StructuredDataExtractor().extract(artifact) == []

    def test_malformed_jsonld_is_skipped(self) -> None:
        artifact = RawArtifact(
            raw_artifact_id="s3://raw-artifacts/test/broken.html",
            url="https://example-vendor.com/x",
            content=('<script type="application/ld+json">{ not valid json </script>'),
            fetched_at=datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
        )
        assert StructuredDataExtractor().extract(artifact) == []
