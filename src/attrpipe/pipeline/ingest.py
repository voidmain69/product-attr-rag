"""Synchronous ingestion pipeline (docs/00 §6 worked example).

One call turns a URL into persisted canonical facts:

    fetch (static, polite) -> Raw Store -> extract (tiered) -> normalize ->
    resolve product -> append-only fact store.

External-IO collaborators (the fetcher and the Raw Store) are Protocols so the
orchestration is unit-testable without a network or object store.
"""

from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel

from attrpipe.core.logging import get_logger
from attrpipe.domain import CandidateFact, RawArtifact
from attrpipe.extraction.base import Extractor
from attrpipe.normalization import Normalizer
from attrpipe.storage import FactRepository, ProductRef, ProductRepository

logger = get_logger(__name__)

# A failed normalization is routed to the queue that a human can act on (docs/06 §4).
_REASON_QUEUE: dict[str, str] = {
    "unmapped": "attribute_mapping",
    "unparseable": "value_anomaly",
    "out_of_constraints": "value_anomaly",
}


class Fetcher(Protocol):
    def fetch(self, url: str) -> RawArtifact: ...


class RawArtifactSink(Protocol):
    def put(self, artifact: RawArtifact) -> str: ...


class HitlSink(Protocol):
    def enqueue(
        self,
        queue: Any,
        payload: dict[str, Any],
        *,
        priority: int = ...,
        dedup: str | None = ...,
    ) -> str | None: ...


class IngestResult(BaseModel):
    url: str
    raw_artifact_id: str
    product_id: str
    candidates: int
    facts_written: int
    facts_unmapped: int
    hitl_enqueued: int


class IngestPipeline:
    def __init__(
        self,
        fetcher: Fetcher,
        raw_store: RawArtifactSink,
        extractors: list[Extractor],
        normalizer: Normalizer,
        products: ProductRepository,
        facts: FactRepository,
        hitl: HitlSink | None = None,
    ) -> None:
        self._fetcher = fetcher
        self._raw_store = raw_store
        self._extractors = extractors
        self._normalizer = normalizer
        self._products = products
        self._facts = facts
        self._hitl = hitl

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
        enqueued = 0
        for candidate in candidates:
            fact, reason = self._normalizer.normalize_result(candidate, product_id, stamp)
            if fact is not None:
                self._facts.upsert(fact)
                written += 1
            elif self._route_to_hitl(candidate, reason, artifact):
                enqueued += 1

        logger.info(
            "ingest_done",
            url=url,
            product_id=product_id,
            candidates=len(candidates),
            facts_written=written,
            hitl_enqueued=enqueued,
        )
        return IngestResult(
            url=url,
            raw_artifact_id=artifact.raw_artifact_id,
            product_id=product_id,
            candidates=len(candidates),
            facts_written=written,
            facts_unmapped=len(candidates) - written,
            hitl_enqueued=enqueued,
        )

    def _route_to_hitl(self, candidate: CandidateFact, reason: str, artifact: RawArtifact) -> bool:
        queue = _REASON_QUEUE.get(reason)
        if self._hitl is None or queue is None:
            return False
        payload = {
            "raw_attribute": candidate.raw_attribute,
            "raw_value": candidate.raw_value,
            "raw_unit": candidate.raw_unit,
            "source_url": artifact.source_url,
            "reason": reason,
        }
        dedup = (
            candidate.raw_attribute
            if reason == "unmapped"
            else f"{candidate.raw_attribute}:{candidate.raw_value}"
        )
        return self._hitl.enqueue(queue, payload, dedup=dedup) is not None


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
