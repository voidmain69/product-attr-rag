"""Query understanding — map a question to a canonical attribute (docs/05 §2).

Deterministic first pass: no LLM. The requested attribute is resolved with the
same synonym dictionary the normalization layer uses (docs/03 §2.1), so a query
and the stored data speak the same vocabulary. Longest phrase wins, so
"battery life" beats "battery". Returns None when nothing matches — the caller
turns that into an explicit clarification, never a guess.
"""

from attrpipe.normalization.attribute_map import normalize_label
from attrpipe.normalization.ontology import ONTOLOGY, CanonicalAttribute


class AttributeQueryParser:
    def __init__(self, ontology: dict[str, CanonicalAttribute] | None = None) -> None:
        source = ontology if ontology is not None else ONTOLOGY
        self._phrases: list[tuple[str, str]] = []
        for attr in source.values():
            labels = (attr.attribute_key, *attr.synonyms, *attr.display_name.values())
            for label in labels:
                normalized = normalize_label(label)
                if normalized:
                    self._phrases.append((normalized, attr.attribute_key))
        # longest phrase first for greedy, unambiguous matching
        self._phrases.sort(key=lambda item: len(item[0]), reverse=True)

    def parse(self, question: str) -> str | None:
        haystack = f" {normalize_label(question)} "
        for phrase, attribute_key in self._phrases:
            if f" {phrase} " in haystack:
                return attribute_key
        return None
