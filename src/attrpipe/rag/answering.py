"""Answering — fact-first exact lookup with citations (docs/05 §3, §5).

Deterministic route A: resolve the product and the requested attribute, then
read the effective canonical fact and format it with its citation and date.
The value is taken verbatim from the fact — the service never fabricates a
number. When the product, the attribute, or the fact cannot be resolved, the
result is an explicit "unknown"/clarification, not a guess (CLAUDE.md §2.6).
"""

from datetime import datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel

from attrpipe.domain import CanonicalFact
from attrpipe.rag.query import AttributeQueryParser


class Route(StrEnum):
    EXACT_LOOKUP = "exact_lookup"
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


class Citation(BaseModel):
    source_url: str
    source_span: str
    fetched_at: datetime


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
    ) -> None:
        self._products = products
        self._facts = facts
        self._parser = parser if parser is not None else AttributeQueryParser()

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
        if attribute_key is None:
            return AnswerResult(
                found=False,
                route=Route.AMBIGUOUS,
                answer=(
                    "Could not tell which attribute is being asked about. "
                    "Please name a known attribute (e.g. weight, IP rating, battery life)."
                ),
            )

        resolved_id = product_id or self._products.resolve(
            gtin=gtin, mpn=mpn, brand=brand, model=model
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

        fact = self._facts.get_effective_fact(resolved_id, attribute_key)
        if fact is None:
            return AnswerResult(
                found=False,
                route=Route.REFUSED,
                answer=f"No data for '{attribute_key}' on this product.",
                product_id=resolved_id,
                attribute_key=attribute_key,
            )

        return AnswerResult(
            found=True,
            route=Route.EXACT_LOOKUP,
            answer=_format_answer(fact),
            product_id=resolved_id,
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
