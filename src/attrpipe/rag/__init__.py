"""RAG — fact-first answering (docs/05).

Route A: exact fact lookup (deterministic SQL via safe, parameterized
functions — never raw SQL from an LLM). Route B: hybrid retrieval (metadata
filters -> dense + BM25 -> rerank) as fallback. Answers always carry
citations (source_url + fetched_at) and honest "unknown" when data is absent.
"""

from attrpipe.rag.answering import AnswerResult, AnswerService, Citation, Route
from attrpipe.rag.query import AttributeQueryParser

__all__ = [
    "AnswerResult",
    "AnswerService",
    "AttributeQueryParser",
    "Citation",
    "Route",
]
