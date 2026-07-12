"""Golden-set regression eval for extraction + normalization (docs/06 §2, docs/09 §3).

Deterministic — runs the real Tier 1/2/3 extractors and the normalizer over
curated fixtures and checks the canonical facts against a baseline. No network,
no DB, no LLM (docs/09 §2). This is the release gate for extraction/normalization
changes: a drop below the baseline accuracy fails the build.

Run with: ``pytest -m golden`` (or ``python tools/dev.py golden``).
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from attrpipe.domain import RawArtifact
from attrpipe.extraction import (
    DomHeuristicsExtractor,
    ShopifyAdapter,
    StructuredDataExtractor,
)
from attrpipe.normalization import Normalizer
from attrpipe.quality import answer_accuracy

pytestmark = pytest.mark.golden

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
BASELINE_ACCURACY = 1.0  # every expected canonical value must be reproduced

# fixture -> {attribute_key: expected canonical_value}
GOLDEN_CASES: list[tuple[str, str, dict[str, object]]] = [
    (
        "jsonld__example-vendor.com__acme-model-x.html",
        "text/html",
        {
            "net_weight": 2300.0,
            "ip_rating": "IP67",
            "battery_life": 14.0,
            "bluetooth_version": "5.3",
            "color": "Midnight Black",
            "material": "Aluminium",
        },
    ),
    (
        "dom__example-vendor.com__widget.html",
        "text/html",
        {
            "net_weight": 2300.0,
            "ip_rating": "IP67",
            "battery_life": 14.0,
            "color": "Midnight Black",
            "material": "Aluminium",
        },
    ),
    (
        "shopify__vendor.myshopify.com__acme-model-x.json",
        "application/json",
        {"net_weight": 2300.0, "color": "Midnight Black"},
    ),
]

_HTML_EXTRACTORS = [StructuredDataExtractor(), DomHeuristicsExtractor()]
_JSON_EXTRACTORS = [ShopifyAdapter()]


def _canonicalize(name: str, content_type: str) -> dict[str, object]:
    artifact = RawArtifact(
        raw_artifact_id=f"golden/{name}",
        url="https://example-vendor.com/products/x",
        content=(FIXTURES / name).read_text(encoding="utf-8"),
        content_type=content_type,
        fetched_at=datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
    )
    extractors = _JSON_EXTRACTORS if content_type == "application/json" else _HTML_EXTRACTORS
    normalizer = Normalizer()
    now = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)
    canonical: dict[str, object] = {}
    for extractor in extractors:
        for candidate in extractor.extract(artifact):
            fact = normalizer.normalize(candidate, "prd_golden", now)
            if fact is not None:
                canonical.setdefault(fact.attribute_key, fact.canonical_value)
    return canonical


@pytest.mark.parametrize(("name", "content_type", "expected"), GOLDEN_CASES)
def test_golden_case(name: str, content_type: str, expected: dict[str, object]) -> None:
    got = _canonicalize(name, content_type)
    results = [(got.get(key), value) for key, value in expected.items()]
    accuracy = answer_accuracy(results)
    missing = {k: v for k, v in expected.items() if got.get(k) != v}
    assert accuracy >= BASELINE_ACCURACY, f"{name}: accuracy {accuracy:.2f}, mismatches: {missing}"


def test_golden_set_overall_accuracy() -> None:
    results: list[tuple[object, object]] = []
    for name, content_type, expected in GOLDEN_CASES:
        got = _canonicalize(name, content_type)
        results.extend((got.get(key), value) for key, value in expected.items())
    assert answer_accuracy(results) >= BASELINE_ACCURACY
