from datetime import UTC, datetime
from pathlib import Path

from attrpipe.domain import CandidateFact, RawArtifact
from attrpipe.domain.facts import ExtractionTier
from attrpipe.extraction import ExtractedFact, LlmExtractor
from attrpipe.normalization import Normalizer

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def load() -> RawArtifact:
    return RawArtifact(
        raw_artifact_id="raw/example-vendor.com/prose",
        url="https://example-vendor.com/products/acme-model-x",
        canonical_url="https://example-vendor.com/products/acme-model-x",
        content=(FIXTURES / "richtext__example-vendor.com__acme-prose.html").read_text(
            encoding="utf-8"
        ),
        fetched_at=datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
    )


class FakeModel:
    """Returns canned extractions — some grounded, some hallucinated."""

    def __init__(self, facts: list[ExtractedFact]) -> None:
        self._facts = facts
        self.calls: list[list[str]] = []

    def extract(
        self, *, text: str, attribute_keys: list[str], product_hint: str | None = None
    ) -> list[ExtractedFact]:
        self.calls.append(attribute_keys)
        return self._facts


GROUNDED = [
    ExtractedFact(
        attribute="battery life",
        value="14",
        unit="hours",
        source_span="It runs for up to 14 hours",
        confidence=0.9,
    ),
    ExtractedFact(
        attribute="IP rating",
        value="IP67",
        unit=None,
        source_span="Rated IP67, it shrugs off rain and dust",
        confidence=0.95,
    ),
]

HALLUCINATED_SPAN = ExtractedFact(
    attribute="warranty",
    value="5 years",
    unit=None,
    source_span="Comes with a 5 year warranty",  # not in the source text
    confidence=0.8,
)

VALUE_NOT_IN_SPAN = ExtractedFact(
    attribute="battery life",
    value="20",  # span says 14, not 20
    unit="hours",
    source_span="It runs for up to 14 hours",
    confidence=0.8,
)


def make_extractor(facts: list[ExtractedFact]) -> LlmExtractor:
    return LlmExtractor(FakeModel(facts), attribute_keys=["battery_life", "ip_rating"])


class TestGrounding:
    def test_grounded_facts_kept(self) -> None:
        facts = make_extractor(GROUNDED).extract(load())
        by_attr = {f.raw_attribute: f for f in facts}
        assert by_attr["battery life"].raw_value == "14"
        assert by_attr["IP rating"].raw_value == "IP67"

    def test_hallucinated_span_dropped(self) -> None:
        facts = make_extractor([*GROUNDED, HALLUCINATED_SPAN]).extract(load())
        assert all(f.raw_attribute != "warranty" for f in facts)
        assert len(facts) == 2

    def test_value_not_in_span_dropped(self) -> None:
        facts = make_extractor([VALUE_NOT_IN_SPAN]).extract(load())
        assert facts == []

    def test_confidence_is_capped(self) -> None:
        fact = make_extractor(GROUNDED).extract(load())[1]  # IP rating, model said 0.95
        assert fact.confidence == 0.85  # LLM_CONFIDENCE_CAP

    def test_tier4_provenance(self) -> None:
        fact = make_extractor(GROUNDED).extract(load())[0]
        assert fact.provenance.extraction_tier == ExtractionTier.LLM
        assert fact.provenance.extraction_method == "llm_structured_v1"
        assert fact.provenance.source_type == "llm_text"


class TestFeedsNormalization:
    def test_prose_facts_normalize(self) -> None:
        candidates = make_extractor(GROUNDED).extract(load())
        normalizer = Normalizer()
        now = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)
        canonical: dict[str, CandidateFact] = {}
        for candidate in candidates:
            fact = normalizer.normalize(candidate, "prd_1", now)
            if fact is not None:
                canonical[fact.attribute_key] = fact
        # "battery life" 14 hours -> battery_life 14 h ; "IP rating" IP67 -> ip_rating
        assert canonical["battery_life"].canonical_value == 14.0
        assert canonical["battery_life"].canonical_unit == "h"
        assert canonical["ip_rating"].canonical_value == "IP67"
