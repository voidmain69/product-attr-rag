from datetime import UTC, datetime
from pathlib import Path

import pytest

from attrpipe.domain import CandidateFact, RawArtifact
from attrpipe.domain.facts import ExtractionTier
from attrpipe.extraction import DomHeuristicsExtractor
from attrpipe.normalization import Normalizer

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def load(name: str) -> RawArtifact:
    return RawArtifact(
        raw_artifact_id=f"raw/example-vendor.com/{name}",
        url="https://example-vendor.com/products/widget-pro",
        canonical_url="https://example-vendor.com/products/widget-pro",
        content=(FIXTURES / name).read_text(encoding="utf-8"),
        fetched_at=datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
    )


@pytest.fixture
def facts() -> dict[str, CandidateFact]:
    artifact = load("dom__example-vendor.com__widget.html")
    return {f.raw_attribute: f for f in DomHeuristicsExtractor().extract(artifact)}


class TestDomExtractor:
    def test_extracts_table_and_dl(self, facts: dict[str, CandidateFact]) -> None:
        assert set(facts) >= {"Net weight", "IP rating", "Colour", "Battery life", "Material"}

    def test_quantity_unit_is_split_out(self, facts: dict[str, CandidateFact]) -> None:
        weight = facts["Net weight"]
        assert weight.raw_value == "2.3"
        assert weight.raw_unit == "kg"

    def test_non_quantity_kept_as_text(self, facts: dict[str, CandidateFact]) -> None:
        assert facts["IP rating"].raw_value == "IP67"
        assert facts["IP rating"].raw_unit is None

    def test_three_column_row_ignored(self, facts: dict[str, CandidateFact]) -> None:
        assert "Price" not in facts  # only two-cell rows are treated as key/value

    def test_tier3_provenance(self, facts: dict[str, CandidateFact]) -> None:
        battery = facts["Battery life"]
        assert battery.provenance.extraction_tier == ExtractionTier.DOM_HEURISTICS
        assert battery.provenance.extraction_method == "dom_heuristics_v1"
        assert battery.confidence == pytest.approx(0.6)

    def test_grounding_invariant(self, facts: dict[str, CandidateFact]) -> None:
        artifact = load("dom__example-vendor.com__widget.html")
        for fact in facts.values():
            assert fact.raw_value in artifact.content


class TestDomFeedsNormalization:
    def test_pipeline_to_canonical(self, facts: dict[str, CandidateFact]) -> None:
        # DOM candidates normalize just like structured ones: "2.3 kg" -> 2300 g.
        normalizer = Normalizer()
        now = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)
        canonical = {
            f.attribute_key: f
            for c in facts.values()
            if (f := normalizer.normalize(c, "prd_1", now)) is not None
        }
        assert canonical["net_weight"].canonical_value == 2300.0
        assert canonical["net_weight"].canonical_unit == "g"
        assert canonical["battery_life"].canonical_value == 14.0
        assert canonical["ip_rating"].canonical_value == "IP67"
