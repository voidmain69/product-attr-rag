"""Quality & operations metrics (docs/06 §1).

Pure functions that compute the layer-quality metrics used by the golden-set
regression gate (docs/06 §2, docs/09 §3) and by operational dashboards
(docs/08): extraction tier distribution, grounding rate, auto-map rate, answer
accuracy, and RAG route distribution.
"""

from attrpipe.quality.benchmark import (
    AttributeOutcome,
    BenchmarkCase,
    BenchmarkReport,
    CaseResult,
    GroupMetrics,
    discover_cases,
    evaluate,
    evaluate_root,
    run_case,
)
from attrpipe.quality.metrics import (
    answer_accuracy,
    auto_map_rate,
    grounding_rate,
    route_distribution,
    tier_distribution,
)

__all__ = [
    "AttributeOutcome",
    "BenchmarkCase",
    "BenchmarkReport",
    "CaseResult",
    "GroupMetrics",
    "answer_accuracy",
    "auto_map_rate",
    "discover_cases",
    "evaluate",
    "evaluate_root",
    "grounding_rate",
    "route_distribution",
    "run_case",
    "tier_distribution",
]
