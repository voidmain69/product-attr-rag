"""Synchronous ingestion pipeline (docs/00 §6 worked example).

One call turns a URL into persisted canonical facts:

    fetch (static, polite) -> Raw Store -> extract (tiered) -> normalize ->
    resolve product -> append-only fact store.

External-IO collaborators (the fetcher and the Raw Store) are Protocols so the
orchestration is unit-testable without a network or object store.
"""

from datetime import UTC, datetime
from typing import Protocol

from pydantic import BaseModel

from attrpipe.core.logging import get_logger
from attrpipe.domain import CandidateFact, RawArtifact
from attrpipe.extraction.base import Extractor
from attrpipe.normalization import Normalizer
from attrpipe.storage import FactRepository, ProductRef, ProductRepository

logger = get_logger(__name__)


class Fetcher(Protocol):
    def fetch(self, url: str) -> RawArtifact: ...


class RawArtifactSink(Protocol):
    def put(self, artifact: RawArtifact) -> str: ...


class IngestResult(BaseModel):
    url: str
    raw_artifact_id: str
    product_id: str
    candidates: int
    facts_written: int
    facts_unmapped: int


class IngestPipeline:
    def __init__(
        self,
        fetcher: Fetcher,
        raw_store: RawArtifactSink,
        extractors: list[Extractor],
        normalizer: Normalizer,
        products: ProductRepository,
        facts: FactRepository,
    ) -> None:
        self._fetcher = fetcher
        self._raw_store = raw_store
        self._extractors = extractors
        self._normalizer = normalizer
        self._products = products
        self._facts = facts

    def ingest(
        self,
        url: str,
        product: ProductRef,
        valid_from: datetime | None = None,
    ) -> IngestResult:
        stamp = valid_from if valid_from is not None else datetime.now(UTC)

        artifact = self._fetcher.fetch(url)
        self._raw_store.put(artifact)

        candidates = [c for extractor in self._extractors for c in extractor.extract(artifact)]

        ref = _enrich_ref(product, candidates, artifact)
        product_id = self._products.resolve_or_create(ref)

        written = 0
        for candidate in candidates:
            fact = self._normalizer.normalize(candidate, product_id, stamp)
            if fact is not None:
                self._facts.upsert(fact)
                written += 1

        logger.info(
            "ingest_done",
            url=url,
            product_id=product_id,
            candidates=len(candidates),
            facts_written=written,
        )
        return IngestResult(
            url=url,
            raw_artifact_id=artifact.raw_artifact_id,
            product_id=product_id,
            candidates=len(candidates),
            facts_written=written,
            facts_unmapped=len(candidates) - written,
        )


def _enrich_ref(
    product: ProductRef, candidates: list[CandidateFact], artifact: RawArtifact
) -> ProductRef:
    """Fill missing GTIN/MPN from extracted identifiers and attach the source URL."""
    detected: dict[str, str] = {}
    for candidate in candidates:
        for key, value in candidate.detected_ids.items():
            detected.setdefault(key, value)
    return product.model_copy(
        update={
            "gtin": product.gtin or detected.get("gtin"),
            "mpn": product.mpn or detected.get("mpn"),
            "source_url": artifact.source_url,
        }
    )
