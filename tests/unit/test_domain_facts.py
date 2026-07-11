from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from attrpipe.domain import CandidateFact, CanonicalFact, EvidenceLocation, Provenance
from attrpipe.domain.facts import DataType, ExtractionTier


def make_provenance(**overrides: object) -> Provenance:
    defaults: dict[str, object] = {
        "source_type": "json_ld",
        "source_url": "https://vendor.com/products/model-x",
        "extraction_tier": ExtractionTier.STRUCTURED_DATA,
        "extraction_method": "json_ld_v1",
        "source_span": '"weight": "2.3 kg"',
        "raw_artifact_id": "s3://raw-artifacts/vendor.com/abc123.html",
        "fetched_at": datetime(2026, 7, 10, 12, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Provenance(**defaults)  # type: ignore[arg-type]


class TestCandidateFact:
    def test_valid_candidate(self) -> None:
        fact = CandidateFact(
            raw_attribute="Вес нетто",
            raw_value="2.3",
            raw_unit="кг",
            confidence=0.88,
            provenance=make_provenance(),
            evidence_location=EvidenceLocation(type="html", selector="div.desc > p"),
        )
        assert fact.raw_attribute == "Вес нетто"
        assert fact.provenance.extraction_tier == ExtractionTier.STRUCTURED_DATA

    @pytest.mark.parametrize("confidence", [-0.1, 1.1])
    def test_confidence_bounds(self, confidence: float) -> None:
        with pytest.raises(ValidationError):
            CandidateFact(
                raw_attribute="weight",
                raw_value="2.3",
                confidence=confidence,
                provenance=make_provenance(),
                evidence_location=EvidenceLocation(type="html"),
            )

    def test_provenance_is_mandatory(self) -> None:
        with pytest.raises(ValidationError):
            CandidateFact(  # type: ignore[call-arg]
                raw_attribute="weight",
                raw_value="2.3",
                confidence=0.9,
                evidence_location=EvidenceLocation(type="html"),
            )


class TestCanonicalFact:
    def test_versioned_fact(self) -> None:
        fact = CanonicalFact(
            product_id="prd_01H",
            attribute_key="net_weight",
            ontology_version=4,
            data_type=DataType.QUANTITY,
            canonical_value=2300,
            canonical_unit="g",
            original_value="2.3 кг",
            confidence=0.94,
            provenance=make_provenance(),
            valid_from=datetime(2026, 7, 10, 12, 5, tzinfo=UTC),
        )
        assert fact.effective is True
        assert fact.disputed is False
        assert fact.superseded_by is None
