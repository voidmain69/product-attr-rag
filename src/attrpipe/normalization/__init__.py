"""Normalization — canonical ontology mapping and entity resolution (docs/03).

Attribute mapping cascade: dictionary -> embedding similarity -> LLM judge ->
human-in-the-loop. Values converted to canonical units; products matched by
GTIN > MPN+brand > brand+model > fuzzy. Conflicts resolved explicitly, never
by silent overwrite.
"""

from attrpipe.normalization.attribute_map import DictionaryAttributeMapper
from attrpipe.normalization.conflict import ConflictResolver, Decision
from attrpipe.normalization.normalizer import Normalizer
from attrpipe.normalization.ontology import ONTOLOGY, ONTOLOGY_VERSION, CanonicalAttribute

__all__ = [
    "ONTOLOGY",
    "ONTOLOGY_VERSION",
    "CanonicalAttribute",
    "ConflictResolver",
    "Decision",
    "DictionaryAttributeMapper",
    "Normalizer",
]
