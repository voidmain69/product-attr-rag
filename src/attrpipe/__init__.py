"""attrpipe — fact-first pipeline for product attribute harvesting.

Layers (each maps to a doc in docs/):
    discovery      01 — finding product URLs (sitemaps, feeds, listings)
    fetch          01 — static/headless fetchers, politeness, raw store
    extraction     02 — tiered extraction (structured data -> CMS -> DOM -> LLM)
    normalization  03 — ontology mapping, value/unit normalization, entity resolution
    storage        04 — canonical fact store, chunking, hybrid indexes
    rag            05 — query understanding, fact-first routing, generation
    core           cross-cutting: config, logging, telemetry
"""

__version__ = "0.1.0"
