"""Extraction — tiered candidate-fact extraction from raw artifacts (docs/02).

Cost cascade: Tier 1 structured data -> Tier 2 CMS adapters -> Tier 3 DOM
heuristics -> Tier 4 LLM. A tier only runs on what previous tiers did not
cover. Reads exclusively from the Raw Store, never from live sites.
"""

from attrpipe.extraction.base import Extractor
from attrpipe.extraction.tier1_structured import StructuredDataExtractor
from attrpipe.extraction.tier2_shopify import ShopifyAdapter
from attrpipe.extraction.tier3_dom import DomHeuristicsExtractor

__all__ = [
    "DomHeuristicsExtractor",
    "Extractor",
    "ShopifyAdapter",
    "StructuredDataExtractor",
]
