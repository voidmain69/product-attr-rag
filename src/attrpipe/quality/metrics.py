"""Quality metric computations (docs/06 §1). Pure — no I/O, no state.

Each function takes already-collected observations and returns a scalar or a
distribution, so the same code serves the golden-set gate and the ops
dashboards. Ratios return 0.0 on an empty input rather than raising.
"""

from collections import Counter
from collections.abc import Sequence


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def answer_accuracy(results: Sequence[tuple[object, object]]) -> float:
    """Fraction of (got, expected) pairs that match exactly (docs/06 §1 RAG)."""
    correct = sum(1 for got, expected in results if got == expected)
    return _ratio(correct, len(results))


def auto_map_rate(auto_mapped: int, total: int) -> float:
    """Share of attributes mapped without HITL — should rise over time (docs/06 §1)."""
    return _ratio(auto_mapped, total)


def grounding_rate(grounded: int, total: int) -> float:
    """Share of LLM facts that passed span verification (docs/06 §1 extraction)."""
    return _ratio(grounded, total)


def _distribution(labels: Sequence[object]) -> dict[str, float]:
    counts = Counter(str(label) for label in labels)
    total = sum(counts.values())
    return {label: _ratio(count, total) for label, count in sorted(counts.items())}


def tier_distribution(tiers: Sequence[object]) -> dict[str, float]:
    """How much of extraction is closed by each tier — cheap Tier 1-3 vs LLM (docs/06 §1)."""
    return _distribution(tiers)


def route_distribution(routes: Sequence[object]) -> dict[str, float]:
    """RAG route mix — rising exact_lookup usually means rising precision (docs/06 §1)."""
    return _distribution(routes)
