"""Core fact models — the contract between pipeline layers.

Candidate facts come out of extraction (docs/02); canonical facts come out of
normalization (docs/03) and are what the fact store persists (docs/04).
Provenance is mandatory everywhere: no fact without a source, a timestamp and
a verbatim span (docs/00, cross-cutting requirements).
"""

from datetime import datetime
from enum import IntEnum, StrEnum

from pydantic import BaseModel, Field


class ExtractionTier(IntEnum):
    STRUCTURED_DATA = 1  # JSON-LD / microdata / embedded framework JSON
    CMS_ADAPTER = 2  # known selectors / API endpoints per engine
    DOM_HEURISTICS = 3  # spec tables, dl-lists, key:value patterns
    LLM = 4  # structured output from rich text / PDF / vision


class DataType(StrEnum):
    QUANTITY = "quantity"
    ENUM = "enum"
    BOOLEAN = "boolean"
    TEXT = "text"
    RANGE = "range"
    DATE = "date"


class EvidenceLocation(BaseModel):
    """Where exactly in the artifact the value was found."""

    type: str  # html | json | pdf | image
    selector: str | None = None  # CSS/XPath for html
    json_path: str | None = None  # for embedded JSON
    page: int | None = None  # for PDF
    bbox: tuple[float, float, float, float] | None = None  # for images


class Provenance(BaseModel):
    source_type: str  # feed | api | json_ld | cms_adapter | dom | llm_text | llm_vision
    source_url: str
    extraction_tier: ExtractionTier
    extraction_method: str  # versioned, e.g. "llm_structured_v3"
    source_span: str  # verbatim quote from the source the value was taken from
    raw_artifact_id: str  # pointer into the Raw Store — enables re-extraction
    fetched_at: datetime


class CandidateFact(BaseModel):
    """Extraction output: attribute/value as seen in the source, not yet canonical."""

    raw_attribute: str
    raw_value: str
    raw_unit: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: Provenance
    evidence_location: EvidenceLocation
    detected_ids: dict[str, str] = Field(default_factory=dict)  # gtin / mpn / brand ...


class CanonicalFact(BaseModel):
    """Normalization output: versioned, canonical, provenance-carrying fact."""

    product_id: str
    attribute_key: str
    ontology_version: int
    data_type: DataType
    canonical_value: str | float | bool | None
    canonical_unit: str | None = None
    original_value: str
    effective: bool = True
    disputed: bool = False
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: Provenance
    valid_from: datetime
    superseded_by: str | None = None
