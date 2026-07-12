"""Tier 3 — DOM heuristics for spec tables and definition lists (docs/02 §4).

For pages with neither structured data nor a known CMS adapter: extract
key/value pairs from two-column ``<table>`` rows and ``<dl>`` lists. Deterministic
but lower confidence than Tier 1; every candidate carries the row text as its
``source_span`` so downstream can verify it (docs/02 §5).
"""

import re
from html.parser import HTMLParser

from attrpipe.core.logging import get_logger
from attrpipe.domain import CandidateFact, EvidenceLocation, Provenance, RawArtifact
from attrpipe.domain.facts import ExtractionTier

logger = get_logger(__name__)

DOM_CONFIDENCE = 0.6
_MAX_VALUE_LEN = 120
_CELL_TAGS = frozenset({"td", "th"})
_WS_RE = re.compile(r"\s+")
# A value that is exactly "<number> <unit>" is split so normalization sees the unit.
_QUANTITY_RE = re.compile(r"^([-+]?\d+(?:[.,]\d+)?)\s*([A-Za-zµ°%/]+)?$")
_KNOWN_UNITS = frozenset(
    {
        "g",
        "kg",
        "mg",
        "oz",
        "lb",
        "mm",
        "cm",
        "m",
        "in",
        "h",
        "hr",
        "min",
        "s",
        "ms",
        "hz",
        "khz",
        "mhz",
        "ghz",
        "w",
        "kw",
        "mb",
        "gb",
        "tb",
    }
)


def _clean(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def _split_quantity(value: str) -> tuple[str, str | None]:
    """Split "2.3 kg" into ("2.3", "kg"); leave non-quantity text as-is."""
    match = _QUANTITY_RE.match(value)
    if match is None:
        return value, None
    number, unit = match.group(1), match.group(2)
    if unit is not None and unit.lower() in _KNOWN_UNITS:
        return number, unit
    return value, None


class _SpecCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.pairs: list[tuple[str, str]] = []
        self._cells: list[str] = []
        self._buf: list[str] = []
        self._open_kind: str | None = None
        self._pending_dt: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._cells = []
        elif tag in _CELL_TAGS or tag in ("dt", "dd"):
            self._open_kind = tag
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag in _CELL_TAGS and self._open_kind in _CELL_TAGS:
            self._cells.append(_clean("".join(self._buf)))
            self._open_kind = None
        elif tag == "tr":
            if len(self._cells) == 2 and self._cells[0] and self._cells[1]:
                self.pairs.append((self._cells[0], self._cells[1]))
            self._cells = []
        elif tag == "dt" and self._open_kind == "dt":
            self._pending_dt = _clean("".join(self._buf))
            self._open_kind = None
        elif tag == "dd" and self._open_kind == "dd":
            value = _clean("".join(self._buf))
            if self._pending_dt and value:
                self.pairs.append((self._pending_dt, value))
            self._pending_dt = None
            self._open_kind = None

    def handle_data(self, data: str) -> None:
        if self._open_kind is not None:
            self._buf.append(data)


class DomHeuristicsExtractor:
    """Tier 3 extractor over spec tables and definition lists."""

    tier = ExtractionTier.DOM_HEURISTICS
    method = "dom_heuristics_v1"

    def extract(self, artifact: RawArtifact) -> list[CandidateFact]:
        collector = _SpecCollector()
        try:
            collector.feed(artifact.content)
        except Exception:
            logger.warning("dom_parse_failed", raw_artifact_id=artifact.raw_artifact_id)
            return []

        facts: list[CandidateFact] = []
        for key, raw in collector.pairs:
            if not key or not raw or len(raw) > _MAX_VALUE_LEN:
                continue
            value, unit = _split_quantity(raw)
            facts.append(
                CandidateFact(
                    raw_attribute=key,
                    raw_value=value,
                    raw_unit=unit,
                    confidence=DOM_CONFIDENCE,
                    provenance=Provenance(
                        source_type="dom",
                        source_url=artifact.source_url,
                        extraction_tier=self.tier,
                        extraction_method=self.method,
                        source_span=f"{key}: {raw}",
                        raw_artifact_id=artifact.raw_artifact_id,
                        fetched_at=artifact.fetched_at,
                    ),
                    evidence_location=EvidenceLocation(type="html", selector="table/dl"),
                )
            )
        return facts
