from datetime import UTC, datetime
from pathlib import Path

import pytest

from attrpipe.domain import CanonicalFact, RawArtifact
from attrpipe.extraction import StructuredDataExtractor
from attrpipe.normalization import Normalizer
from attrpipe.pipeline import IngestPipeline
from attrpipe.storage import ProductRef

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
VALID_FROM = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)


class FakeFetcher:
    def __init__(self, artifact: RawArtifact) -> None:
        self._artifact = artifact

    def fetch(self, url: str) -> RawArtifact:
        return self._artifact


class FakeSink:
    def __init__(self) -> None:
        self.puts: list[str] = []

    def put(self, artifact: RawArtifact) -> str:
        self.puts.append(artifact.raw_artifact_id)
        return "hash"


class FakeProductRepo:
    def __init__(self) -> None:
        self.ref: ProductRef | None = None

    def resolve_or_create(self, ref: ProductRef) -> str:
        self.ref = ref
        return "prd_test"


class FakeFactRepo:
    def __init__(self) -> None:
        self.upserts: list[CanonicalFact] = []

    def upsert(self, fact: CanonicalFact) -> str:
        self.upserts.append(fact)
        return f"fct_{fact.attribute_key}"


@pytest.fixture
def artifact() -> RawArtifact:
    content = (FIXTURES / "jsonld__example-vendor.com__acme-model-x.html").read_text(
        encoding="utf-8"
    )
    return RawArtifact(
        raw_artifact_id="raw/example-vendor.com/abc",
        url="https://example-vendor.com/products/acme-model-x",
        canonical_url="https://example-vendor.com/products/acme-model-x",
        content=content,
        fetched_at=datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
    )


@pytest.fixture
def parts(artifact: RawArtifact) -> tuple[IngestPipeline, FakeSink, FakeProductRepo, FakeFactRepo]:
    sink, products, facts = FakeSink(), FakeProductRepo(), FakeFactRepo()
    pipeline = IngestPipeline(
        fetcher=FakeFetcher(artifact),
        raw_store=sink,
        extractors=[StructuredDataExtractor()],
        normalizer=Normalizer(),
        products=products,  # type: ignore[arg-type]
        facts=facts,  # type: ignore[arg-type]
    )
    return pipeline, sink, products, facts


class TestIngestPipeline:
    def test_end_to_end_counts(
        self, parts: tuple[IngestPipeline, FakeSink, FakeProductRepo, FakeFactRepo]
    ) -> None:
        pipeline, _, _, _ = parts
        result = pipeline.ingest(
            "https://example-vendor.com/products/acme-model-x",
            ProductRef(brand="Acme", model="Model X"),
            valid_from=VALID_FROM,
        )
        assert result.product_id == "prd_test"
        assert result.facts_written == 6
        assert result.facts_unmapped == 1  # price has no canonical mapping yet

    def test_artifact_is_persisted_before_extraction(
        self, parts: tuple[IngestPipeline, FakeSink, FakeProductRepo, FakeFactRepo]
    ) -> None:
        pipeline, sink, _, _ = parts
        pipeline.ingest(
            "https://example-vendor.com/products/acme-model-x",
            ProductRef(brand="Acme", model="Model X"),
            valid_from=VALID_FROM,
        )
        assert sink.puts == ["raw/example-vendor.com/abc"]

    def test_product_ref_enriched_from_detected_ids(
        self, parts: tuple[IngestPipeline, FakeSink, FakeProductRepo, FakeFactRepo]
    ) -> None:
        pipeline, _, products, _ = parts
        pipeline.ingest(
            "https://example-vendor.com/products/acme-model-x",
            ProductRef(brand="Acme", model="Model X"),
            valid_from=VALID_FROM,
        )
        assert products.ref is not None
        assert products.ref.gtin == "4006381333931"  # filled from JSON-LD
        assert products.ref.mpn == "MX-001"
        assert products.ref.source_url == "https://example-vendor.com/products/acme-model-x"

    def test_written_facts_are_canonical(
        self, parts: tuple[IngestPipeline, FakeSink, FakeProductRepo, FakeFactRepo]
    ) -> None:
        pipeline, _, _, facts = parts
        pipeline.ingest(
            "https://example-vendor.com/products/acme-model-x",
            ProductRef(brand="Acme", model="Model X"),
            valid_from=VALID_FROM,
        )
        by_key = {f.attribute_key: f for f in facts.upserts}
        assert by_key["net_weight"].canonical_value == 2300.0
        assert by_key["net_weight"].canonical_unit == "g"
        assert set(by_key) == {
            "net_weight",
            "battery_life",
            "ip_rating",
            "bluetooth_version",
            "color",
            "material",
        }
