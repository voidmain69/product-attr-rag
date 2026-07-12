"""Tier 1 — structured-data extraction from JSON-LD (docs/02 §2).

The cheapest, most accurate source: ``schema.org/Product`` markup that the
manufacturer publishes for search engines. Deterministic, high confidence,
no network and no LLM. Values are taken verbatim, so every candidate carries
a ``source_span`` for grounding (docs/02 §5.3).

Scope of this module: JSON-LD ``<script type="application/ld+json">`` blocks.
Embedded framework JSON (``__NEXT_DATA__`` etc.) and microdata are separate
follow-ups in the same tier.
"""

import json
from html.parser import HTMLParser
from typing import Any

from attrpipe.core.logging import get_logger
from attrpipe.domain import CandidateFact, EvidenceLocation, Provenance, RawArtifact
from attrpipe.domain.facts import ExtractionTier

logger = get_logger(__name__)

STRUCTURED_CONFIDENCE = 0.95

# Scalar schema.org properties that are genuine product specs (not identity).
# Identity fields (name/brand/gtin/mpn/sku) are collected into detected_ids instead.
_SCALAR_SPEC_KEYS = ("color", "material", "size", "pattern")
# Properties expressed as a value + unit (schema.org QuantitativeValue).
_QUANTITY_SPEC_KEYS = ("weight", "height", "width", "depth")


class _JsonLdCollector(HTMLParser):
    """Collect the text of every ``application/ld+json`` script block."""

    def __init__(self) -> None:
        super().__init__()
        self._in_ld = False
        self.blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and dict(attrs).get("type") == "application/ld+json":
            self._in_ld = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_ld = False

    def handle_data(self, data: str) -> None:
        if self._in_ld and data.strip():
            self.blocks.append(data)


def _iter_nodes(parsed: Any) -> list[dict[str, Any]]:
    """Flatten a JSON-LD document into candidate nodes (handles @graph and lists)."""
    nodes: list[dict[str, Any]] = []
    stack: list[Any] = [parsed]
    while stack:
        item = stack.pop()
        if isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, dict):
            nodes.append(item)
            graph = item.get("@graph")
            if isinstance(graph, list):
                stack.extend(graph)
    return nodes


def _is_product(node: dict[str, Any]) -> bool:
    node_type = node.get("@type")
    if isinstance(node_type, str):
        return node_type == "Product"
    if isinstance(node_type, list):
        return "Product" in node_type
    return False


def _detected_ids(node: dict[str, Any]) -> dict[str, str]:
    ids: dict[str, str] = {}
    for key in ("sku", "mpn"):
        value = node.get(key)
        if isinstance(value, str | int):
            ids[key] = str(value)
    for key in ("gtin13", "gtin8", "gtin12", "gtin14", "gtin"):
        value = node.get(key)
        if isinstance(value, str | int):
            ids["gtin"] = str(value)
            break
    brand = node.get("brand")
    if isinstance(brand, dict) and isinstance(brand.get("name"), str):
        ids["brand"] = brand["name"]
    elif isinstance(brand, str):
        ids["brand"] = brand
    return ids


class StructuredDataExtractor:
    """Tier 1 extractor over JSON-LD ``schema.org/Product`` blocks."""

    tier = ExtractionTier.STRUCTURED_DATA
    method = "jsonld_v1"

    def extract(self, artifact: RawArtifact) -> list[CandidateFact]:
        collector = _JsonLdCollector()
        try:
            collector.feed(artifact.content)
        except Exception:
            logger.warning("jsonld_parse_failed", raw_artifact_id=artifact.raw_artifact_id)
            return []

        facts: list[CandidateFact] = []
        for block in collector.blocks:
            try:
                parsed = json.loads(block)
            except json.JSONDecodeError:
                logger.warning("jsonld_invalid", raw_artifact_id=artifact.raw_artifact_id)
                continue
            for node in _iter_nodes(parsed):
                if _is_product(node):
                    facts.extend(self._facts_from_product(node, artifact))
        return facts

    def _facts_from_product(
        self, node: dict[str, Any], artifact: RawArtifact
    ) -> list[CandidateFact]:
        detected = _detected_ids(node)
        facts: list[CandidateFact] = []

        def add(raw_attribute: str, raw_value: str, raw_unit: str | None, json_path: str) -> None:
            facts.append(
                CandidateFact(
                    raw_attribute=raw_attribute,
                    raw_value=raw_value,
                    raw_unit=raw_unit,
                    confidence=STRUCTURED_CONFIDENCE,
                    detected_ids=detected,
                    provenance=Provenance(
                        source_type="json_ld",
                        source_url=artifact.source_url,
                        extraction_tier=self.tier,
                        extraction_method=self.method,
                        source_span=json.dumps({raw_attribute: raw_value}, ensure_ascii=False),
                        raw_artifact_id=artifact.raw_artifact_id,
                        fetched_at=artifact.fetched_at,
                    ),
                    evidence_location=EvidenceLocation(type="json", json_path=json_path),
                )
            )

        for key in _SCALAR_SPEC_KEYS:
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                add(key, value, None, f"$.{key}")

        for key in _QUANTITY_SPEC_KEYS:
            parsed = _quantity(node.get(key))
            if parsed is not None:
                value, unit = parsed
                add(key, value, unit, f"$.{key}")

        offers = node.get("offers")
        price = _offer_price(offers)
        if price is not None:
            value, unit = price
            add("price", value, unit, "$.offers.price")

        extra = node.get("additionalProperty")
        if isinstance(extra, list):
            for i, prop in enumerate(extra):
                parsed_prop = _property_value(prop)
                if parsed_prop is not None:
                    name, value, unit = parsed_prop
                    add(name, value, unit, f"$.additionalProperty[{i}]")

        return facts


def _quantity(value: Any) -> tuple[str, str | None] | None:
    """Parse a scalar or schema.org QuantitativeValue into (value, unit)."""
    if isinstance(value, str | int | float) and not isinstance(value, bool):
        text = str(value).strip()
        return (text, None) if text else None
    if isinstance(value, dict):
        raw = value.get("value")
        if isinstance(raw, str | int | float) and not isinstance(raw, bool):
            unit = value.get("unitText") or value.get("unitCode")
            return str(raw), unit if isinstance(unit, str) else None
    return None


def _offer_price(offers: Any) -> tuple[str, str | None] | None:
    node = offers[0] if isinstance(offers, list) and offers else offers
    if not isinstance(node, dict):
        return None
    price = node.get("price")
    if isinstance(price, str | int | float) and not isinstance(price, bool):
        currency = node.get("priceCurrency")
        return str(price), currency if isinstance(currency, str) else None
    return None


def _property_value(prop: Any) -> tuple[str, str, str | None] | None:
    """Parse a schema.org PropertyValue into (name, value, unit)."""
    if not isinstance(prop, dict):
        return None
    name = prop.get("name")
    value = prop.get("value")
    if not isinstance(name, str) or not name.strip():
        return None
    if not (isinstance(value, str | int | float) and not isinstance(value, bool)):
        return None
    unit = prop.get("unitText") or prop.get("unitCode")
    return name, str(value), unit if isinstance(unit, str) else None
