"""Normalizer — candidate fact -> canonical fact (docs/03 §2-3, §6).

Deterministic core of the normalization layer: map the raw attribute to a
canonical key, normalize the value to the attribute's canonical form/unit, and
emit a versioned CanonicalFact carrying the same provenance. Entity resolution
(assigning ``product_id``) and conflict resolution are separate stages; this
component takes an already-resolved ``product_id``.

An unmapped attribute or an unparseable value yields ``None`` — an explicit
"don't know how to canonicalize this yet" that downstream routes to HITL,
never a guessed value (CLAUDE.md §2.6).
"""

from datetime import datetime

from attrpipe.core.logging import get_logger
from attrpipe.domain import CandidateFact, CanonicalFact
from attrpipe.domain.facts import DataType
from attrpipe.normalization.attribute_map import DictionaryAttributeMapper
from attrpipe.normalization.ontology import ONTOLOGY_VERSION, get_attribute
from attrpipe.normalization.units import normalize_quantity

logger = get_logger(__name__)


class Normalizer:
    def __init__(self, mapper: DictionaryAttributeMapper | None = None) -> None:
        self._mapper = mapper if mapper is not None else DictionaryAttributeMapper()

    def normalize(
        self,
        candidate: CandidateFact,
        product_id: str,
        valid_from: datetime,
    ) -> CanonicalFact | None:
        attribute_key = self._mapper.map(candidate.raw_attribute)
        if attribute_key is None:
            logger.info("attribute_unmapped", raw_attribute=candidate.raw_attribute)
            return None

        attribute = get_attribute(attribute_key)
        if attribute is None:  # pragma: no cover - mapper only yields known keys
            return None

        original_value = _original_value(candidate)
        canonical_value: str | float | bool | None
        canonical_unit: str | None

        if attribute.data_type == DataType.QUANTITY and attribute.canonical_unit is not None:
            number = normalize_quantity(
                candidate.raw_value, candidate.raw_unit, attribute.canonical_unit
            )
            if number is None:
                logger.info(
                    "value_unparseable",
                    attribute_key=attribute_key,
                    raw_value=candidate.raw_value,
                )
                return None
            if not _within_constraints(number, attribute.value_constraints):
                logger.warning(
                    "value_out_of_constraints",
                    attribute_key=attribute_key,
                    canonical_value=number,
                )
                return None
            canonical_value = number
            canonical_unit = attribute.canonical_unit
        else:
            canonical_value = candidate.raw_value.strip()
            canonical_unit = None

        return CanonicalFact(
            product_id=product_id,
            attribute_key=attribute_key,
            ontology_version=ONTOLOGY_VERSION,
            data_type=attribute.data_type,
            canonical_value=canonical_value,
            canonical_unit=canonical_unit,
            original_value=original_value,
            confidence=candidate.confidence,
            provenance=candidate.provenance,
            valid_from=valid_from,
        )


def _original_value(candidate: CandidateFact) -> str:
    if candidate.raw_unit:
        return f"{candidate.raw_value} {candidate.raw_unit}".strip()
    return candidate.raw_value


def _within_constraints(value: float, constraints: dict[str, float] | None) -> bool:
    if not constraints:
        return True
    if "min" in constraints and value < constraints["min"]:
        return False
    return not ("max" in constraints and value > constraints["max"])
