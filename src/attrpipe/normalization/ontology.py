"""Canonical attribute ontology (docs/03 §1).

A versioned, category-organized model of attributes. This module ships a small
in-code ontology for the accuracy-MVP (one category — headphones); seeding it
into the ``attributes_ontology`` table is a separate storage-layer concern.

Ontology changes are versioned, never rewritten in place (CLAUDE.md §2.4).
"""

from pydantic import BaseModel

from attrpipe.domain.facts import DataType

ONTOLOGY_VERSION = 1


class CanonicalAttribute(BaseModel):
    attribute_key: str
    category_path: tuple[str, ...]
    display_name: dict[str, str]
    data_type: DataType
    canonical_unit: str | None = None
    allowed_units: tuple[str, ...] = ()
    value_constraints: dict[str, float] | None = None
    enum_values: tuple[str, ...] | None = None
    synonyms: tuple[str, ...] = ()


_HEADPHONES = ("electronics", "audio", "headphones")

_ATTRIBUTES: tuple[CanonicalAttribute, ...] = (
    CanonicalAttribute(
        attribute_key="net_weight",
        category_path=_HEADPHONES,
        display_name={"uk": "Вага нетто", "en": "Net weight"},
        data_type=DataType.QUANTITY,
        canonical_unit="g",
        allowed_units=("g", "kg", "mg", "oz", "lb"),
        value_constraints={"min": 0, "max": 500000},
        synonyms=("weight", "net weight", "mass", "вага", "маса", "вес", "вес нетто"),
    ),
    CanonicalAttribute(
        attribute_key="battery_life",
        category_path=_HEADPHONES,
        display_name={"uk": "Час автономної роботи", "en": "Battery life"},
        data_type=DataType.QUANTITY,
        canonical_unit="h",
        allowed_units=("h", "min", "s"),
        value_constraints={"min": 0, "max": 1000},
        synonyms=("battery life", "battery", "автономність", "час роботи", "время работы"),
    ),
    CanonicalAttribute(
        attribute_key="ip_rating",
        category_path=_HEADPHONES,
        display_name={"uk": "Клас захисту", "en": "IP rating"},
        data_type=DataType.TEXT,
        synonyms=("ip rating", "ip", "protection class", "клас захисту", "степень защиты"),
    ),
    CanonicalAttribute(
        attribute_key="bluetooth_version",
        category_path=_HEADPHONES,
        display_name={"uk": "Версія Bluetooth", "en": "Bluetooth version"},
        data_type=DataType.TEXT,
        synonyms=("bluetooth", "bluetooth version", "версія bluetooth", "версия bluetooth"),
    ),
    CanonicalAttribute(
        attribute_key="color",
        category_path=_HEADPHONES,
        display_name={"uk": "Колір", "en": "Color"},
        data_type=DataType.TEXT,
        synonyms=("color", "colour", "колір", "цвет"),
    ),
    CanonicalAttribute(
        attribute_key="material",
        category_path=_HEADPHONES,
        display_name={"uk": "Матеріал", "en": "Material"},
        data_type=DataType.TEXT,
        synonyms=("material", "матеріал", "материал"),
    ),
)

ONTOLOGY: dict[str, CanonicalAttribute] = {a.attribute_key: a for a in _ATTRIBUTES}


def get_attribute(attribute_key: str) -> CanonicalAttribute | None:
    return ONTOLOGY.get(attribute_key)
