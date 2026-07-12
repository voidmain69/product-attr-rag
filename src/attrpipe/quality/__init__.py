"""Quality & operations metrics (docs/06 §1).

Pure functions that compute the layer-quality metrics used by the golden-set
regression gate (docs/06 §2, docs/09 §3) and by operational dashboards
(docs/08): extraction tier distribution, grounding rate, auto-map rate, answer
accuracy, and RAG route distribution.
"""

from attrpipe.quality.metrics import (
    answer_accuracy,
    auto_map_rate,
    grounding_rate,
    route_distribution,
    tier_distribution,
)

__all__ = [
    "answer_accuracy",
    "auto_map_rate",
    "grounding_rate",
    "route_distribution",
    "tier_distribution",
]
