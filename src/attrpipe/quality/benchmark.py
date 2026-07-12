"""Universal extraction benchmark harness (docs/06 §2, docs/09 §3).

Data-driven measurement of *attribute extraction* across vendors and product
categories. Cases live in a directory tree — no code change is needed to add a
vendor or a category::

    <root>/<vendor>/<category>/<slug>/
        source.html           # or source.json — the saved raw artifact
        expected.json         # product identity + expected canonical values

``expected.json`` shape::

    {
      "product": {"brand": "ASUS", "name": "ROG STRIX B650E-F", "source_url": "..."},
      "content_type": "text/html",          # optional; inferred from the source file
      "expected": {"socket": "AM5", "form_factor": "ATX", "memory_slots": 4}
    }

The harness runs the real deterministic cascade (Tier 1 JSON-LD + Tier 3 DOM,
or Tier 2 for JSON) and the normalizer — no network, no LLM (docs/09 §2) — then
scores accuracy and coverage per vendor, per category and overall, plus the
extraction-tier mix. It is the *measurement* surface; the golden gate
(tests/golden) is the pass/fail regression surface built on the same primitives.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from attrpipe.domain import RawArtifact
from attrpipe.extraction import (
    DomHeuristicsExtractor,
    ShopifyAdapter,
    StructuredDataExtractor,
)
from attrpipe.extraction.base import Extractor
from attrpipe.normalization import Normalizer

# Deterministic timestamps — the benchmark must be reproducible (docs/00 idempotency).
_BENCH_TS = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

# Source file name -> content type. First match wins when a case has several.
_SOURCE_FILES: tuple[tuple[str, str], ...] = (
    ("source.html", "text/html"),
    ("source.json", "application/json"),
)

OutcomeStatus = Literal["correct", "wrong", "missing"]


def default_extractors(content_type: str) -> list[Extractor]:
    """The deterministic tiers to run for a content type (cheapest-first)."""
    if "json" in content_type:
        return [ShopifyAdapter()]
    return [StructuredDataExtractor(), DomHeuristicsExtractor()]


@dataclass(frozen=True)
class BenchmarkCase:
    vendor: str
    category: str
    slug: str
    content_type: str
    source_path: Path
    expected: dict[str, object]
    product: dict[str, object] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return f"{self.vendor}/{self.category}/{self.slug}"


@dataclass(frozen=True)
class AttributeOutcome:
    attribute_key: str
    expected: object
    got: object | None
    status: OutcomeStatus
    tier: int | None


@dataclass(frozen=True)
class CaseResult:
    case: BenchmarkCase
    outcomes: list[AttributeOutcome]

    @property
    def n_expected(self) -> int:
        return len(self.outcomes)

    @property
    def n_correct(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "correct")

    @property
    def n_wrong(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "wrong")

    @property
    def n_missing(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "missing")

    @property
    def accuracy(self) -> float:
        return self.n_correct / self.n_expected if self.n_expected else 0.0

    @property
    def coverage(self) -> float:
        """Share of expected attributes for which *some* value was extracted."""
        found = self.n_correct + self.n_wrong
        return found / self.n_expected if self.n_expected else 0.0


@dataclass(frozen=True)
class GroupMetrics:
    n_cases: int
    n_expected: int
    n_correct: int
    n_wrong: int
    n_missing: int
    tier_counts: dict[str, int]

    @property
    def accuracy(self) -> float:
        return self.n_correct / self.n_expected if self.n_expected else 0.0

    @property
    def coverage(self) -> float:
        found = self.n_correct + self.n_wrong
        return found / self.n_expected if self.n_expected else 0.0


@dataclass(frozen=True)
class BenchmarkReport:
    results: list[CaseResult]
    overall: GroupMetrics
    by_vendor: dict[str, GroupMetrics]
    by_category: dict[str, GroupMetrics]
    by_vendor_category: dict[str, GroupMetrics]

    def to_dict(self) -> dict[str, object]:
        return {
            "overall": _metrics_to_dict(self.overall),
            "by_vendor": {k: _metrics_to_dict(v) for k, v in self.by_vendor.items()},
            "by_category": {k: _metrics_to_dict(v) for k, v in self.by_category.items()},
            "by_vendor_category": {
                k: _metrics_to_dict(v) for k, v in self.by_vendor_category.items()
            },
            "cases": [_case_to_dict(r) for r in self.results],
        }


def discover_cases(root: Path) -> list[BenchmarkCase]:
    """Find every ``expected.json`` under ``<root>/<vendor>/<category>/<slug>/``."""
    cases: list[BenchmarkCase] = []
    for expected_path in sorted(root.glob("*/*/*/expected.json")):
        slug_dir = expected_path.parent
        meta = json.loads(expected_path.read_text(encoding="utf-8"))
        source_path, content_type = _resolve_source(slug_dir, meta)
        cases.append(
            BenchmarkCase(
                vendor=slug_dir.parent.parent.name,
                category=slug_dir.parent.name,
                slug=slug_dir.name,
                content_type=content_type,
                source_path=source_path,
                expected=dict(meta["expected"]),
                product=dict(meta.get("product", {})),
            )
        )
    return cases


def run_case(
    case: BenchmarkCase,
    normalizer: Normalizer | None = None,
    extractors: Sequence[Extractor] | None = None,
) -> CaseResult:
    """Run the deterministic cascade over one case and score it against expected."""
    normalizer = normalizer if normalizer is not None else Normalizer()
    tiers = extractors if extractors is not None else default_extractors(case.content_type)

    artifact = RawArtifact(
        raw_artifact_id=f"benchmark/{case.name}",
        url=str(case.product.get("source_url", f"https://benchmark.local/{case.slug}")),
        content=case.source_path.read_text(encoding="utf-8"),
        content_type=case.content_type,
        fetched_at=_BENCH_TS,
    )

    canonical: dict[str, object] = {}
    tier_by_key: dict[str, int] = {}
    for extractor in tiers:
        for candidate in extractor.extract(artifact):
            fact = normalizer.normalize(candidate, "prd_benchmark", _BENCH_TS)
            if fact is not None and fact.attribute_key not in canonical:
                canonical[fact.attribute_key] = fact.canonical_value
                tier_by_key[fact.attribute_key] = int(candidate.provenance.extraction_tier)

    outcomes: list[AttributeOutcome] = []
    for key, expected_value in case.expected.items():
        if key in canonical:
            got = canonical[key]
            status: OutcomeStatus = "correct" if _matches(got, expected_value) else "wrong"
            outcomes.append(AttributeOutcome(key, expected_value, got, status, tier_by_key[key]))
        else:
            outcomes.append(AttributeOutcome(key, expected_value, None, "missing", None))
    return CaseResult(case=case, outcomes=outcomes)


def evaluate(cases: Sequence[BenchmarkCase]) -> BenchmarkReport:
    """Run and aggregate every case into a full report."""
    results = [run_case(c) for c in cases]
    return BenchmarkReport(
        results=results,
        overall=_aggregate(results),
        by_vendor=_group_by(results, lambda r: r.case.vendor),
        by_category=_group_by(results, lambda r: r.case.category),
        by_vendor_category=_group_by(results, lambda r: f"{r.case.vendor}/{r.case.category}"),
    )


def evaluate_root(root: Path) -> BenchmarkReport:
    """Convenience: discover and evaluate every case under ``root``."""
    return evaluate(discover_cases(root))


def _resolve_source(slug_dir: Path, meta: dict[str, object]) -> tuple[Path, str]:
    override = meta.get("content_type")
    for filename, content_type in _SOURCE_FILES:
        candidate = slug_dir / filename
        if candidate.exists():
            return candidate, str(override) if isinstance(override, str) else content_type
    raise FileNotFoundError(f"no source.* file in {slug_dir}")


def _matches(got: object, expected: object) -> bool:
    if _is_number(got) and _is_number(expected):
        return math.isclose(float(got), float(expected), rel_tol=1e-9, abs_tol=1e-6)  # type: ignore[arg-type]
    return got == expected


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _group_by(
    results: Sequence[CaseResult], key: Callable[[CaseResult], str]
) -> dict[str, GroupMetrics]:
    buckets: dict[str, list[CaseResult]] = {}
    for result in results:
        buckets.setdefault(key(result), []).append(result)
    return {name: _aggregate(bucket) for name, bucket in sorted(buckets.items())}


def _aggregate(results: Sequence[CaseResult]) -> GroupMetrics:
    tier_counts: Counter[str] = Counter()
    for result in results:
        for outcome in result.outcomes:
            if outcome.tier is not None and outcome.status != "missing":
                tier_counts[str(outcome.tier)] += 1
    return GroupMetrics(
        n_cases=len(results),
        n_expected=sum(r.n_expected for r in results),
        n_correct=sum(r.n_correct for r in results),
        n_wrong=sum(r.n_wrong for r in results),
        n_missing=sum(r.n_missing for r in results),
        tier_counts=dict(sorted(tier_counts.items())),
    )


def _metrics_to_dict(m: GroupMetrics) -> dict[str, object]:
    return {
        "n_cases": m.n_cases,
        "n_expected": m.n_expected,
        "n_correct": m.n_correct,
        "n_wrong": m.n_wrong,
        "n_missing": m.n_missing,
        "accuracy": round(m.accuracy, 4),
        "coverage": round(m.coverage, 4),
        "tier_counts": m.tier_counts,
    }


def _case_to_dict(r: CaseResult) -> dict[str, object]:
    return {
        "name": r.case.name,
        "accuracy": round(r.accuracy, 4),
        "coverage": round(r.coverage, 4),
        "outcomes": [
            {
                "attribute_key": o.attribute_key,
                "status": o.status,
                "expected": o.expected,
                "got": o.got,
                "tier": o.tier,
            }
            for o in r.outcomes
        ],
    }
