"""Self-contained chunking for hybrid retrieval (docs/04 §4).

The main cause of poor spec retrieval is context-free chunks: "Weight: 2.3 kg"
finds the weight of *any* product. Every chunk here carries a product header
(brand, model, category) and serializes facts attribute-by-attribute into prose,
so dense/lexical search cannot mix up products (docs/04 §4.1).
"""

from datetime import datetime

from pydantic import BaseModel

from attrpipe.domain import CanonicalFact
from attrpipe.storage.db import generate_id
from attrpipe.storage.product_repository import ProductRecord


class Chunk(BaseModel):
    chunk_id: str
    product_id: str
    kind: str
    body: str
    attribute_keys: list[str]
    brand: str | None
    category_path: list[str]
    source_url: str | None
    fetched_at: datetime | None


class Chunker:
    def fact_chunk(self, product: ProductRecord, facts: list[CanonicalFact]) -> Chunk | None:
        """Serialize a product's effective facts into one self-contained fact chunk."""
        if not facts:
            return None
        header = (
            f"[Brand: {product.brand}] [Model: {product.model}] "
            f"[Category: {'/'.join(product.category_path)}]"
        )
        lines = [header]
        for fact in facts:
            label = fact.attribute_key.replace("_", " ")
            unit = f" {fact.canonical_unit}" if fact.canonical_unit else ""
            lines.append(f"{label}: {fact.canonical_value}{unit}.")

        latest = max(facts, key=lambda f: f.provenance.fetched_at)
        source_url = latest.provenance.source_url
        fetched_at = latest.provenance.fetched_at
        lines.append(f"Source: {source_url}, as of {fetched_at.date().isoformat()}.")

        return Chunk(
            chunk_id=generate_id("chk"),
            product_id=product.product_id,
            kind="fact",
            body="\n".join(lines),
            attribute_keys=sorted({f.attribute_key for f in facts}),
            brand=product.brand,
            category_path=product.category_path,
            source_url=source_url,
            fetched_at=fetched_at,
        )
