from datetime import UTC, datetime

from attrpipe.domain import CanonicalFact, Provenance
from attrpipe.domain.facts import DataType, ExtractionTier
from attrpipe.normalization import ConflictResolver

BASE = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)


def fact(
    *,
    value: object,
    source_type: str,
    source_url: str,
    tier: ExtractionTier,
    fetched_at: datetime = BASE,
    confidence: float = 0.9,
) -> CanonicalFact:
    return CanonicalFact(
        product_id="prd_1",
        attribute_key="net_weight",
        ontology_version=1,
        data_type=DataType.QUANTITY,
        canonical_value=value,
        canonical_unit="g",
        original_value=f"{value} g",
        confidence=confidence,
        provenance=Provenance(
            source_type=source_type,
            source_url=source_url,
            extraction_tier=tier,
            extraction_method="m",
            source_span="span",
            raw_artifact_id="s3://raw/x",
            fetched_at=fetched_at,
        ),
        valid_from=BASE,
    )


class TestConflictResolver:
    def setup_method(self) -> None:
        self.resolver = ConflictResolver()

    def test_same_source_supersedes(self) -> None:
        current = fact(
            value=2300.0,
            source_type="json_ld",
            source_url="u1",
            tier=ExtractionTier.STRUCTURED_DATA,
        )
        newer = fact(
            value=2400.0,
            source_type="json_ld",
            source_url="u1",
            tier=ExtractionTier.STRUCTURED_DATA,
            fetched_at=datetime(2026, 7, 11, 12, 0, tzinfo=UTC),
        )
        decision = self.resolver.decide(current, newer)
        assert decision.supersede is True
        assert decision.effective_is_candidate is True
        assert decision.disputed is False

    def test_higher_authority_wins_no_dispute(self) -> None:
        dom = fact(
            value=2400.0, source_type="dom", source_url="u2", tier=ExtractionTier.DOM_HEURISTICS
        )
        structured = fact(
            value=2300.0,
            source_type="json_ld",
            source_url="u1",
            tier=ExtractionTier.STRUCTURED_DATA,
        )
        # incoming structured beats existing dom
        decision = self.resolver.decide(dom, structured)
        assert decision.effective_is_candidate is True
        assert decision.disputed is False  # different authority -> not a dispute

    def test_lower_authority_loses(self) -> None:
        structured = fact(
            value=2300.0,
            source_type="json_ld",
            source_url="u1",
            tier=ExtractionTier.STRUCTURED_DATA,
        )
        dom = fact(
            value=2400.0, source_type="dom", source_url="u2", tier=ExtractionTier.DOM_HEURISTICS
        )
        decision = self.resolver.decide(structured, dom)
        assert decision.effective_is_candidate is False
        assert decision.disputed is False

    def test_equal_authority_disagreement_is_disputed(self) -> None:
        a = fact(
            value=2300.0,
            source_type="json_ld",
            source_url="u1",
            tier=ExtractionTier.STRUCTURED_DATA,
        )
        b = fact(
            value=2400.0,
            source_type="json_ld",
            source_url="u2",
            tier=ExtractionTier.STRUCTURED_DATA,
            fetched_at=datetime(2026, 7, 11, 12, 0, tzinfo=UTC),
        )
        decision = self.resolver.decide(a, b)
        assert decision.disputed is True
        assert decision.effective_is_candidate is True  # newer wins the tie-break

    def test_equal_authority_same_value_not_disputed(self) -> None:
        a = fact(
            value=2300.0,
            source_type="json_ld",
            source_url="u1",
            tier=ExtractionTier.STRUCTURED_DATA,
        )
        b = fact(
            value=2300.0,
            source_type="json_ld",
            source_url="u2",
            tier=ExtractionTier.STRUCTURED_DATA,
        )
        decision = self.resolver.decide(a, b)
        assert decision.disputed is False  # consensus, not conflict
