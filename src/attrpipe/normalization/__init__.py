"""Normalization — canonical ontology mapping and entity resolution (docs/03).

Attribute mapping cascade: dictionary -> embedding similarity -> LLM judge ->
human-in-the-loop. Values converted to canonical units; products matched by
GTIN > MPN+brand > brand+model > fuzzy. Conflicts resolved explicitly, never
by silent overwrite.
"""
