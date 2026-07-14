from datetime import UTC, datetime

import pytest

from attrpipe.domain import CandidateFact, EvidenceLocation, Provenance
from attrpipe.domain.facts import DataType, ExtractionTier
from attrpipe.normalization import DictionaryAttributeMapper, Normalizer
from attrpipe.normalization.units import convert, normalize_quantity, parse_number

VALID_FROM = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)


def make_candidate(
    raw_attribute: str, raw_value: str, raw_unit: str | None = None
) -> CandidateFact:
    return CandidateFact(
        raw_attribute=raw_attribute,
        raw_value=raw_value,
        raw_unit=raw_unit,
        confidence=0.95,
        provenance=Provenance(
            source_type="json_ld",
            source_url="https://example-vendor.com/products/acme-model-x",
            extraction_tier=ExtractionTier.STRUCTURED_DATA,
            extraction_method="jsonld_v1",
            source_span=f'"{raw_attribute}": "{raw_value}"',
            raw_artifact_id="s3://raw-artifacts/test/x.html",
            fetched_at=datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
        ),
        evidence_location=EvidenceLocation(type="json"),
    )


class TestParseNumber:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("2.3", 2.3), ("2,3", 2.3), ("2300", 2300.0), ("  14 ", 14.0), ("-5", -5.0)],
    )
    def test_parses(self, raw: str, expected: float) -> None:
        assert parse_number(raw) == expected

    def test_unparseable(self) -> None:
        assert parse_number("n/a") is None


class TestConvert:
    def test_kg_to_g(self) -> None:
        assert convert(2.3, "kg", "g") == 2300.0

    def test_missing_unit_assumed_canonical(self) -> None:
        assert convert(2300, None, "g") == 2300.0

    def test_cross_dimension_rejected(self) -> None:
        assert convert(1, "kg", "h") is None

    def test_unknown_unit_rejected(self) -> None:
        assert convert(1, "furlong", "g") is None

    def test_quantity_with_comma_and_unit(self) -> None:
        assert normalize_quantity("2,3", "kg", "g") == 2300.0


class TestAttributeMapper:
    def setup_method(self) -> None:
        self.mapper = DictionaryAttributeMapper()

    @pytest.mark.parametrize(
        ("raw", "key"),
        [
            ("weight", "net_weight"),
            ("Вес нетто", "net_weight"),
            ("Net weight", "net_weight"),
            ("IP rating", "ip_rating"),
            ("Battery life", "battery_life"),
            ("colour", "color"),
            ("Матеріал", "material"),
        ],
    )
    def test_maps_synonyms(self, raw: str, key: str) -> None:
        assert self.mapper.map(raw) == key

    def test_unknown_returns_none(self) -> None:
        assert self.mapper.map("promotional tagline") is None


class TestNormalizer:
    def setup_method(self) -> None:
        self.normalizer = Normalizer()

    def test_quantity_converted_to_canonical(self) -> None:
        fact = self.normalizer.normalize(make_candidate("weight", "2.3", "kg"), "prd_1", VALID_FROM)
        assert fact is not None
        assert fact.attribute_key == "net_weight"
        assert fact.data_type == DataType.QUANTITY
        assert fact.canonical_value == 2300.0
        assert fact.canonical_unit == "g"
        assert fact.original_value == "2.3 kg"
        assert fact.ontology_version == 2

    def test_text_attribute_trimmed(self) -> None:
        fact = self.normalizer.normalize(make_candidate("IP rating", "IP67"), "prd_1", VALID_FROM)
        assert fact is not None
        assert fact.attribute_key == "ip_rating"
        assert fact.canonical_value == "IP67"
        assert fact.canonical_unit is None

    def test_provenance_is_carried_through(self) -> None:
        candidate = make_candidate("weight", "2.3", "kg")
        fact = self.normalizer.normalize(candidate, "prd_1", VALID_FROM)
        assert fact is not None
        assert fact.provenance == candidate.provenance
        assert fact.confidence == 0.95
        assert fact.effective is True
        assert fact.superseded_by is None

    def test_unmapped_attribute_returns_none(self) -> None:
        # Honest "unknown": no canonical key -> no fabricated fact (routes to HITL).
        assert (
            self.normalizer.normalize(make_candidate("price", "199.00", "EUR"), "prd_1", VALID_FROM)
            is None
        )

    def test_out_of_constraints_rejected(self) -> None:
        # 3000 kg = 3_000_000 g exceeds net_weight max (500000) -> anomaly, dropped.
        assert (
            self.normalizer.normalize(make_candidate("weight", "3000", "kg"), "prd_1", VALID_FROM)
            is None
        )

    def test_unparseable_quantity_returns_none(self) -> None:
        assert (
            self.normalizer.normalize(
                make_candidate("weight", "unknown", None), "prd_1", VALID_FROM
            )
            is None
        )
