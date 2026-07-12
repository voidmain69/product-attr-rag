"""Tier 2 — Shopify CMS adapter (docs/02 §3).

Shopify exposes a product's full model at ``/products/<handle>.json``. This
adapter reads that structure directly — no DOM guessing — so a recognized engine
is closed cheaply and accurately, keeping load off the expensive tiers. It is
one entry in a growing library of per-engine adapters.

Applicable only to a Shopify product JSON payload; on anything else it returns
no facts (the cascade moves on to the next tier).
"""

import json
from typing import Any

from attrpipe.core.logging import get_logger
from attrpipe.domain import CandidateFact, EvidenceLocation, Provenance, RawArtifact
from attrpipe.domain.facts import ExtractionTier

logger = get_logger(__name__)

SHOPIFY_CONFIDENCE = 0.9


def _product_node(data: Any) -> dict[str, Any] | None:
    if isinstance(data, dict):
        product = data.get("product")
        if isinstance(product, dict):
            return product
        if "variants" in data:  # the payload may already be the product object
            return data
    return None


def _detected_ids(product: dict[str, Any], variant: dict[str, Any]) -> dict[str, str]:
    ids: dict[str, str] = {}
    vendor = product.get("vendor")
    if isinstance(vendor, str) and vendor.strip():
        ids["brand"] = vendor
    sku = variant.get("sku")
    if isinstance(sku, str | int) and str(sku).strip():
        ids["sku"] = str(sku)
    barcode = variant.get("barcode")
    if isinstance(barcode, str | int) and str(barcode).strip():
        ids["gtin"] = str(barcode)
    return ids


def _weight(variant: dict[str, Any]) -> tuple[str, str] | None:
    grams = variant.get("grams")
    if isinstance(grams, int | float) and not isinstance(grams, bool) and grams > 0:
        return str(grams), "g"
    value = variant.get("weight")
    unit = variant.get("weight_unit")
    if isinstance(value, int | float) and not isinstance(value, bool) and isinstance(unit, str):
        return str(value), unit
    return None


class ShopifyAdapter:
    """Tier 2 extractor over a Shopify product JSON payload."""

    tier = ExtractionTier.CMS_ADAPTER
    method = "shopify_json_v1"

    def extract(self, artifact: RawArtifact) -> list[CandidateFact]:
        try:
            data = json.loads(artifact.content)
        except json.JSONDecodeError:
            return []
        product = _product_node(data)
        if product is None:
            return []

        variants = product.get("variants")
        variant = (
            variants[0]
            if isinstance(variants, list) and variants and isinstance(variants[0], dict)
            else {}
        )
        detected = _detected_ids(product, variant)
        facts: list[CandidateFact] = []

        def add(raw_attribute: str, raw_value: str, raw_unit: str | None, json_path: str) -> None:
            facts.append(
                CandidateFact(
                    raw_attribute=raw_attribute,
                    raw_value=raw_value,
                    raw_unit=raw_unit,
                    confidence=SHOPIFY_CONFIDENCE,
                    detected_ids=detected,
                    provenance=Provenance(
                        source_type="cms_adapter",
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

        weight = _weight(variant)
        if weight is not None:
            add("weight", weight[0], weight[1], "$.product.variants[0].grams")

        price = variant.get("price")
        if isinstance(price, str | int | float) and not isinstance(price, bool):
            add("price", str(price), None, "$.product.variants[0].price")

        options = product.get("options")
        if isinstance(options, list):
            for i, option in enumerate(options):
                single = _single_value_option(option)
                if single is not None:
                    name, value = single
                    add(name, value, None, f"$.product.options[{i}]")

        return facts


def _single_value_option(option: Any) -> tuple[str, str] | None:
    """A product-level attribute is an option with exactly one value (not a variant axis)."""
    if not isinstance(option, dict):
        return None
    name = option.get("name")
    values = option.get("values")
    if not isinstance(name, str) or not isinstance(values, list) or len(values) != 1:
        return None
    value = values[0]
    if not isinstance(value, str) or not value.strip():
        return None
    return name, value
