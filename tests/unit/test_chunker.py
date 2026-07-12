from datetime import UTC, datetime

from attrpipe.domain import CanonicalFact, Provenance
from attrpipe.domain.facts import DataType, ExtractionTier
from attrpipe.storage import Chunker, ProductRecord


def fact(key: str, value: object, unit: str | None) -> CanonicalFact:
    return CanonicalFact(
        product_id="prd_1",
        attribute_key=key,
        ontology_version=1,
        data_type=DataType.QUANTITY if unit else DataType.TEXT,
        canonical_value=value,
        canonical_unit=unit,
        original_value=f"{value}{unit or ''}",
        confidence=0.95,
        provenance=Provenance(
            source_type="json_ld",
            source_url="https://example-vendor.com/products/acme-model-x",
            extraction_tier=ExtractionTier.STRUCTURED_DATA,
            extraction_method="jsonld_v1",
            source_span="span",
            raw_artifact_id="s3://raw/x",
            fetched_at=datetime(2026, 7, 10, 12, 0, tzinfo=UTC),
        ),
        valid_from=datetime(2026, 7, 12, 12, 0, tzinfo=UTC),
    )


PRODUCT = ProductRecord(
    product_id="prd_1",
    brand="Acme",
    model="Model X",
    category_path=["electronics", "audio", "headphones"],
    gtin="4006381333931",
    mpn="MX-001",
    canonical_title="Acme Model X",
    source_urls=["https://example-vendor.com/products/acme-model-x"],
)


class TestChunker:
    def test_chunk_is_self_contained(self) -> None:
        chunk = Chunker().fact_chunk(PRODUCT, [fact("net_weight", 2300.0, "g")])
        assert chunk is not None
        # product header present so retrieval can't mix up products
        assert "[Brand: Acme]" in chunk.body
        assert "[Model: Model X]" in chunk.body
        assert "electronics/audio/headphones" in chunk.body
        assert "net weight: 2300.0 g." in chunk.body
        assert "Source: https://example-vendor.com" in chunk.body

    def test_metadata_carried(self) -> None:
        chunk = Chunker().fact_chunk(
            PRODUCT, [fact("net_weight", 2300.0, "g"), fact("ip_rating", "IP67", None)]
        )
        assert chunk is not None
        assert chunk.brand == "Acme"
        assert chunk.category_path == ["electronics", "audio", "headphones"]
        assert chunk.attribute_keys == ["ip_rating", "net_weight"]

    def test_no_facts_no_chunk(self) -> None:
        assert Chunker().fact_chunk(PRODUCT, []) is None
