"""Tier 4 — LLM extraction from rich content (docs/02 §5).

The most expensive, most flexible tier: it recovers attributes that live only in
prose, PDFs, or images — where deterministic tiers find nothing. The LLM is
called with a closed set of target attribute keys ("fill this schema, null for
what's absent"), and every candidate is grounded before it is trusted:

- the ``source_span`` must appear verbatim in the raw artifact, and
- the value must appear within that span.

A fact that fails grounding is dropped, never guessed (docs/02 §5.3,
CLAUDE.md §2.6). The LLM client is a Protocol so the tier is unit-tested with a
fake — no network, no real model call (docs/09 §2). A concrete Anthropic-backed
model lives in ``extraction.llm_anthropic``.
"""

import re
from typing import Protocol

from pydantic import BaseModel, Field

from attrpipe.core.logging import get_logger
from attrpipe.domain import CandidateFact, EvidenceLocation, Provenance, RawArtifact
from attrpipe.domain.facts import ExtractionTier

logger = get_logger(__name__)

LLM_CONFIDENCE_CAP = 0.85
_WS_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


class ExtractedFact(BaseModel):
    """One fact as returned by the model, before grounding."""

    attribute: str
    value: str
    unit: str | None = None
    source_span: str
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class StructuredExtractionModel(Protocol):
    """Contract for an LLM that fills a closed attribute schema from text."""

    def extract(
        self, *, text: str, attribute_keys: list[str], product_hint: str | None = None
    ) -> list[ExtractedFact]: ...


class LlmExtractor:
    """Tier 4 extractor: schema-guided LLM extraction with grounding verification."""

    tier = ExtractionTier.LLM
    method = "llm_structured_v1"

    def __init__(
        self,
        model: StructuredExtractionModel,
        attribute_keys: list[str],
        *,
        confidence_cap: float = LLM_CONFIDENCE_CAP,
    ) -> None:
        self._model = model
        self._attribute_keys = attribute_keys
        self._confidence_cap = confidence_cap

    def extract(self, artifact: RawArtifact) -> list[CandidateFact]:
        extracted = self._model.extract(text=artifact.content, attribute_keys=self._attribute_keys)
        normalized_content = _normalize(artifact.content)
        facts: list[CandidateFact] = []
        for item in extracted:
            span = item.source_span.strip()
            if not self._is_grounded(item, span, normalized_content, artifact):
                continue
            facts.append(
                CandidateFact(
                    raw_attribute=item.attribute,
                    raw_value=item.value,
                    raw_unit=item.unit,
                    confidence=min(item.confidence, self._confidence_cap),
                    provenance=Provenance(
                        source_type="llm_text",
                        source_url=artifact.source_url,
                        extraction_tier=self.tier,
                        extraction_method=self.method,
                        source_span=span,
                        raw_artifact_id=artifact.raw_artifact_id,
                        fetched_at=artifact.fetched_at,
                    ),
                    evidence_location=EvidenceLocation(type="html"),
                )
            )
        return facts

    def _is_grounded(
        self,
        item: ExtractedFact,
        span: str,
        normalized_content: str,
        artifact: RawArtifact,
    ) -> bool:
        if not span or not item.value.strip():
            return False
        if _normalize(span) not in normalized_content:
            logger.info(
                "llm_span_not_grounded",
                raw_artifact_id=artifact.raw_artifact_id,
                attribute=item.attribute,
            )
            return False
        if item.value.strip().lower() not in span.lower():
            logger.info(
                "llm_value_not_in_span",
                raw_artifact_id=artifact.raw_artifact_id,
                attribute=item.attribute,
            )
            return False
        return True
