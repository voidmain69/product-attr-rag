"""API response models (docs/05). Every fact answer carries its provenance and
freshness so the caller can cite the source and the date (CLAUDE.md §2.1)."""

from datetime import datetime

from pydantic import BaseModel

from attrpipe.domain import CanonicalFact
from attrpipe.domain.facts import DataType
from attrpipe.normalization.ontology import CanonicalAttribute
from attrpipe.storage import FilterOp, ProductRecord


class FactOut(BaseModel):
    attribute_key: str
    canonical_value: str | float | bool | None
    canonical_unit: str | None
    original_value: str
    data_type: DataType
    confidence: float
    disputed: bool
    source_url: str
    source_span: str
    fetched_at: datetime
    valid_from: datetime

    @classmethod
    def from_fact(cls, fact: CanonicalFact) -> "FactOut":
        return cls(
            attribute_key=fact.attribute_key,
            canonical_value=fact.canonical_value,
            canonical_unit=fact.canonical_unit,
            original_value=fact.original_value,
            data_type=fact.data_type,
            confidence=fact.confidence,
            disputed=fact.disputed,
            source_url=fact.provenance.source_url,
            source_span=fact.provenance.source_span,
            fetched_at=fact.provenance.fetched_at,
            valid_from=fact.valid_from,
        )


class ProductOut(BaseModel):
    product_id: str
    brand: str
    model: str
    category_path: list[str]
    gtin: str | None
    mpn: str | None
    canonical_title: str | None
    source_urls: list[str]

    @classmethod
    def from_record(cls, record: ProductRecord) -> "ProductOut":
        return cls(**record.model_dump())


class AnswerIn(BaseModel):
    question: str
    product_id: str | None = None
    gtin: str | None = None
    mpn: str | None = None
    brand: str | None = None
    model: str | None = None


class FilterConstraintIn(BaseModel):
    attribute_key: str
    op: FilterOp = "eq"
    value: str | float | bool


class FilterIn(BaseModel):
    constraints: list[FilterConstraintIn]
    limit: int = 100


class FilterOut(BaseModel):
    product_ids: list[str]
    count: int


class CompareIn(BaseModel):
    product_ids: list[str]
    attribute_keys: list[str]


class CompareCell(BaseModel):
    canonical_value: str | float | bool | None
    canonical_unit: str | None
    original_value: str


class CompareRow(BaseModel):
    product_id: str
    attributes: dict[str, CompareCell]


class CompareOut(BaseModel):
    attribute_keys: list[str]
    rows: list[CompareRow]


class AttributeOut(BaseModel):
    attribute_key: str
    category_path: list[str]
    display_name: dict[str, str]
    data_type: DataType
    canonical_unit: str | None
    allowed_units: list[str]
    synonyms: list[str]

    @classmethod
    def from_attribute(cls, attr: CanonicalAttribute) -> "AttributeOut":
        return cls(
            attribute_key=attr.attribute_key,
            category_path=list(attr.category_path),
            display_name=attr.display_name,
            data_type=attr.data_type,
            canonical_unit=attr.canonical_unit,
            allowed_units=list(attr.allowed_units),
            synonyms=list(attr.synonyms),
        )
