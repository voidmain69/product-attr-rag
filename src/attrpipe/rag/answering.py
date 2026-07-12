"""Answering — fact-first routing with a hybrid-retrieval fallback (docs/05).

Route A (exact lookup): resolve the product and the requested attribute, then
read the effective canonical fact and format it with its citation and date — the
value is taken verbatim, never fabricated. Route B (hybrid retrieval): when the
attribute doesn't map, the product is fuzzy, or the fact is absent — the fuzzy /
rich-content cases — fall back to dense retrieval over self-contained chunks and
answer from the retrieved evidence with its source. When neither route produces
grounded evidence, the result is an explicit "unknown", not a guess (§2.6).
"""

from datetime import datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel

from attrpipe.domain import CanonicalFact
from attrpipe.rag.query import AttributeQueryParser
from attrpipe.storage import ChunkHit


class Route(StrEnum):
    EXACT_LOOKUP = "exact_lookup"
    HYBRID = "hybrid"
    REFUSED = "refused"
    AMBIGUOUS = "ambiguous"


class ProductResolver(Protocol):
    def resolve(
        self,
        *,
        gtin: str | None = None,
        mpn: str | None = None,
        brand: str | None = None,
        model: str | None = None,
    ) -> str | None: ...


class FactLookup(Protocol):
    def get_effective_fact(self, product_id: str, attribute_key: str) -> CanonicalFact | None: ...


class Retriever(Protocol):
    def search(
        self, query: str, *, brand: str | None = None, category: str | None = None, limit: int = 5
    ) -> list[ChunkHit]: ...


class Citation(BaseModel):
    source_url: str
    source_span: str
    fetched_at: datetime | None = None


class AnswerResult(BaseModel):
    found: bool
    route: Route
    answer: str
    product_id: str | None = None
    attribute_key: str | None = None
    canonical_value: str | float | bool | None = None
    canonical_unit: str | None = None
    original_value: str | None = None
    disputed: bool = False
    citation: Citation | None = None


class AnswerService:
    def __init__(
        self,
        products: ProductResolver,
        facts: FactLookup,
        parser: AttributeQueryParser | None = None,
        retriever: Retriever | None = None,
    ) -> None:
        self._products = products
        self._facts = facts
        self._parser = parser if parser is not None else AttributeQueryParser()
        self._retriever = retriever

    def answer(
        self,
        question: str,
        *,
        product_id: str | None = None,
        gtin: str | None = None,
        mpn: str | None = None,
        brand: str | None = None,
        model: str | None = None,
    ) -> AnswerResult:
        attribute_key = self._parser.parse(question)
        resolved_id = product_id or self._products.resolve(
            gtin=gtin, mpn=mpn, brand=brand, model=model
        )

        # Route A — exact fact lookup when both the product and the attribute are known.
        if attribute_key is not None and resolved_id is not None:
            fact = self._facts.get_effective_fact(resolved_id, attribute_key)
            if fact is not None:
                return _exact_result(resolved_id, attribute_key, fact)

        # Route B — hybrid retrieval fallback (fuzzy / rich-content / missing fact).
        if self._retriever is not None:
            hits = self._retriever.search(question, brand=brand, limit=3)
            if hits:
                return _hybrid_result(hits[0], attribute_key)

        # Honest "unknown".
        if attribute_key is None:
            return AnswerResult(
                found=False,
                route=Route.AMBIGUOUS,
                answer=(
                    "Could not tell which attribute is being asked about. "
                    "Please name a known attribute (e.g. weight, IP rating, battery life)."
                ),
            )
        if resolved_id is None:
            return AnswerResult(
                found=False,
                route=Route.REFUSED,
                answer=(
                    "Could not resolve the product. "
                    "Provide product_id, GTIN, MPN, or brand + model."
                ),
                attribute_key=attribute_key,
            )
        return AnswerResult(
            found=False,
            route=Route.REFUSED,
            answer=f"No data for '{attribute_key}' on this product.",
            product_id=resolved_id,
            attribute_key=attribute_key,
        )


def _exact_result(product_id: str, attribute_key: str, fact: CanonicalFact) -> AnswerResult:
    return AnswerResult(
        found=True,
        route=Route.EXACT_LOOKUP,
        answer=_format_answer(fact),
        product_id=product_id,
        attribute_key=attribute_key,
        canonical_value=fact.canonical_value,
        canonical_unit=fact.canonical_unit,
        original_value=fact.original_value,
        disputed=fact.disputed,
        citation=Citation(
            source_url=fact.provenance.source_url,
            source_span=fact.provenance.source_span,
            fetched_at=fact.provenance.fetched_at,
        ),
    )


def _hybrid_result(hit: ChunkHit, attribute_key: str | None) -> AnswerResult:
    return AnswerResult(
        found=True,
        route=Route.HYBRID,
        answer=f"Based on the product's stored data:\n{hit.body}",
        product_id=hit.product_id,
        attribute_key=attribute_key,
        citation=Citation(
            source_url=hit.source_url or "",
            source_span=hit.body,
            fetched_at=hit.fetched_at,
        ),
    )


def _format_answer(fact: CanonicalFact) -> str:
    label = fact.attribute_key.replace("_", " ")
    unit = f" {fact.canonical_unit}" if fact.canonical_unit else ""
    value = f"{fact.canonical_value}{unit}"
    if fact.original_value and fact.original_value != value:
        value = f"{value} (as reported: {fact.original_value})"
    date = fact.provenance.fetched_at.date().isoformat()
    citation = f" Source: {fact.provenance.source_url}, as of {date}."
    if fact.disputed:
        return f"{label}: {value} (sources disagree; see citation).{citation}"
    return f"{label}: {value}.{citation}"
