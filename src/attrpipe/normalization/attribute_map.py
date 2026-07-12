"""Attribute mapping — stage 1, deterministic dictionary (docs/03 §2.1).

Maps a raw attribute label ("Вес нетто", "IP rating") to a canonical
``attribute_key`` via a synonym dictionary built from the ontology. This is the
cheapest, most accurate mapping stage; embedding similarity and an LLM judge
(§2.2–2.3) are later, higher-cost stages for what the dictionary misses.
"""

import re

from attrpipe.normalization.ontology import ONTOLOGY, CanonicalAttribute

_WS_RE = re.compile(r"\s+")


def normalize_label(label: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace for dictionary lookup."""
    cleaned = label.strip().lower().replace("_", " ").replace("-", " ")
    cleaned = re.sub(r"[^\w\s]", " ", cleaned, flags=re.UNICODE)
    return _WS_RE.sub(" ", cleaned).strip()


class DictionaryAttributeMapper:
    """Deterministic raw_attribute -> attribute_key mapper over the ontology."""

    def __init__(
        self,
        ontology: dict[str, CanonicalAttribute] | None = None,
        learned: dict[str, str] | None = None,
    ) -> None:
        source = ontology if ontology is not None else ONTOLOGY
        self._index: dict[str, str] = {}
        for attr in source.values():
            labels = (attr.attribute_key, *attr.synonyms, *attr.display_name.values())
            for label in labels:
                self._index[normalize_label(label)] = attr.attribute_key
        # Human-confirmed mappings (docs/03 §2.4) are authoritative -> applied last.
        for raw_attribute, attribute_key in (learned or {}).items():
            self._index[normalize_label(raw_attribute)] = attribute_key

    def map(self, raw_attribute: str) -> str | None:
        """Return the canonical attribute_key, or ``None`` if unknown (-> HITL)."""
        return self._index.get(normalize_label(raw_attribute))
