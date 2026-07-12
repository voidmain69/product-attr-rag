"""Prometheus metrics for the answering service (docs/08 §2).

``attrpipe_rag_route_total`` tracks how answers are served: growth of the
``exact_lookup`` route relative to ``refused`` is the primary precision signal.
"""

from prometheus_client import Counter, Gauge

rag_route_total = Counter(
    "attrpipe_rag_route_total",
    "RAG answers by route",
    ["route"],  # exact_lookup | refused
)

hitl_queue_depth = Gauge(
    "attrpipe_hitl_queue_depth",
    "Open items per human-in-the-loop queue",
    ["queue"],
)
