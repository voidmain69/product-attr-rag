from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from attrpipe.domain import CandidateFact, EvidenceLocation, Provenance, RawArtifact
from attrpipe.domain.facts import ExtractionTier
from attrpipe.extraction import StructuredDataExtractor
from attrpipe.normalization import Normalizer
from attrpipe.pipeline import IngestPipeline
from attrpipe.storage import ProductRef

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
VALID_FROM = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)


def candidate(raw_attribute: str, raw_value: str, raw_unit: str | None = None) -> CandidateFact:
    return CandidateFact(
        raw_attribute=raw_attribute,
        raw_value=raw_value,
        raw_unit=raw_unit,
        confidence=0.9,
        provenance=Provenance(
            source_type="dom",
            source_url="https://v/x",
            extraction_tier=ExtractionTier.DOM_HEURISTICS,
            extraction_method="m",
            source_span="s",
            raw_artifact_id="s3://x",
            fetched_at=datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
        ),
        evidence_location=EvidenceLocation(type="html"),
    )


class TestNormalizeResultReason:
    def setup_method(self) -> None:
        self.n = Normalizer()

    def test_ok(self) -> None:
        _, reason = self.n.normalize_result(candidate("weight", "2.3", "kg"), "p", VALID_FROM)
        assert reason == "ok"

    def test_unmapped(self) -> None:
        fact, reason = self.n.normalize_result(candidate("promo tagline", "buy"), "p", VALID_FROM)
        assert fact is None
        assert reason == "unmapped"

    def test_out_of_constraints(self) -> None:
        fact, reason = self.n.normalize_result(candidate("weight", "3000", "kg"), "p", VALID_FROM)
        assert fact is None
        assert reason == "out_of_constraints"

    def test_unparseable(self) -> None:
        fact, reason = self.n.normalize_result(candidate("weight", "n/a", None), "p", VALID_FROM)
        assert fact is None
        assert reason == "unparseable"


class FakeFetcher:
    def __init__(self, artifact: RawArtifact) -> None:
        self._a = artifact

    def fetch(self, url: str) -> RawArtifact:
        return self._a


class FakeSink:
    def put(self, artifact: RawArtifact) -> str:
        return "h"


class FakeProductRepo:
    def resolve_or_create(self, ref: ProductRef) -> str:
        return "prd_1"


class FakeFactRepo:
    def upsert(self, fact: Any) -> str:
        return "fct"


class FakeHitl:
    def __init__(self) -> None:
        self.items: list[tuple[str, dict[str, Any], str | None]] = []

    def enqueue(
        self, queue: Any, payload: dict[str, Any], *, priority: int = 100, dedup: str | None = None
    ) -> str | None:
        # emulate dedup: skip if same dedup already present
        if dedup is not None and any(d == dedup for _, _, d in self.items):
            return None
        self.items.append((queue, payload, dedup))
        return "hitl_x"


@pytest.fixture
def artifact() -> RawArtifact:
    content = (FIXTURES / "jsonld__example-vendor.com__acme-model-x.html").read_text(
        encoding="utf-8"
    )
    return RawArtifact(
        raw_artifact_id="raw/x",
        url="https://example-vendor.com/products/acme-model-x",
        canonical_url="https://example-vendor.com/products/acme-model-x",
        content=content,
        fetched_at=datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
    )


class TestPipelineHitlRouting:
    def test_unmapped_price_is_enqueued(self, artifact: RawArtifact) -> None:
        hitl = FakeHitl()
        pipeline = IngestPipeline(
            fetcher=FakeFetcher(artifact),
            raw_store=FakeSink(),
            extractors=[StructuredDataExtractor()],
            normalizer=Normalizer(),
            products=FakeProductRepo(),  # type: ignore[arg-type]
            facts=FakeFactRepo(),  # type: ignore[arg-type]
            hitl=hitl,  # type: ignore[arg-type]
        )
        result = pipeline.ingest(
            "https://example-vendor.com/products/acme-model-x",
            ProductRef(brand="Acme", model="Model X"),
            valid_from=VALID_FROM,
        )
        assert result.facts_written == 6
        assert result.hitl_enqueued == 1  # price -> attribute_mapping queue
        queue, payload, _ = hitl.items[0]
        assert queue == "attribute_mapping"
        assert payload["raw_attribute"] == "price"

    def test_no_hitl_sink_still_works(self, artifact: RawArtifact) -> None:
        pipeline = IngestPipeline(
            fetcher=FakeFetcher(artifact),
            raw_store=FakeSink(),
            extractors=[StructuredDataExtractor()],
            normalizer=Normalizer(),
            products=FakeProductRepo(),  # type: ignore[arg-type]
            facts=FakeFactRepo(),  # type: ignore[arg-type]
        )
        result = pipeline.ingest(
            "https://example-vendor.com/products/acme-model-x",
            ProductRef(brand="Acme", model="Model X"),
            valid_from=VALID_FROM,
        )
        assert result.hitl_enqueued == 0
