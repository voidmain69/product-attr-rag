"""Canonical attribute ontology (docs/03 §1).

A versioned, category-organized model of attributes. This module ships a small
in-code ontology for the accuracy-MVP (one category — headphones); seeding it
into the ``attributes_ontology`` table is a separate storage-layer concern.

Ontology changes are versioned, never rewritten in place (CLAUDE.md §2.4).
"""

from pydantic import BaseModel

from attrpipe.domain.facts import DataType

ONTOLOGY_VERSION = 2  # v2: added PC-component categories (motherboard/monitor/laptop/gpu/cpu)


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
_MOTHERBOARD = ("components", "motherboard")
_MONITOR = ("electronics", "monitor")
_LAPTOP = ("electronics", "laptop")
_GPU = ("components", "graphics_card")
_CPU = ("components", "cpu")
_COMPONENT = ("components",)

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
    # --- Cross-category (shared) attributes -------------------------------
    CanonicalAttribute(
        attribute_key="socket",
        category_path=_CPU,
        display_name={"uk": "Сокет", "en": "Socket"},
        data_type=DataType.TEXT,
        synonyms=(
            "socket",
            "cpu socket",
            "processor socket",
            "socket type",
            "sockets supported",
            "supported sockets",
            "сокет",
            "процесорний роз'єм",
        ),
    ),
    CanonicalAttribute(
        attribute_key="memory_type",
        category_path=_COMPONENT,
        display_name={"uk": "Тип пам'яті", "en": "Memory type"},
        data_type=DataType.TEXT,
        synonyms=("memory type", "type of memory", "тип пам'яті", "тип памяті"),
    ),
    CanonicalAttribute(
        attribute_key="tdp",
        category_path=_COMPONENT,
        display_name={"uk": "Тепловиділення (TDP)", "en": "TDP"},
        data_type=DataType.QUANTITY,
        canonical_unit="w",
        allowed_units=("w", "kw"),
        value_constraints={"min": 0, "max": 2000},
        synonyms=(
            "tdp",
            "thermal design power",
            "default tdp",
            "processor base power",
            "power consumption",
            "tgp",
            "total graphics power",
            "тепловиділення",
        ),
    ),
    CanonicalAttribute(
        attribute_key="screen_size",
        category_path=_MONITOR,
        display_name={"uk": "Діагональ екрана", "en": "Screen size"},
        data_type=DataType.QUANTITY,
        canonical_unit="in",
        allowed_units=("in",),
        value_constraints={"min": 0, "max": 200},
        synonyms=(
            "screen size",
            "display size",
            "panel size",
            "diagonal",
            "screen diagonal",
            "діагональ",
            "розмір екрана",
        ),
    ),
    # --- Motherboards -----------------------------------------------------
    CanonicalAttribute(
        attribute_key="chipset",
        category_path=_MOTHERBOARD,
        display_name={"uk": "Чипсет", "en": "Chipset"},
        data_type=DataType.TEXT,
        synonyms=("chipset", "чипсет", "чіпсет"),
    ),
    CanonicalAttribute(
        attribute_key="form_factor",
        category_path=_MOTHERBOARD,
        display_name={"uk": "Форм-фактор", "en": "Form factor"},
        data_type=DataType.TEXT,
        synonyms=("form factor", "форм фактор", "форм-фактор"),
    ),
    CanonicalAttribute(
        attribute_key="memory_slots",
        category_path=_MOTHERBOARD,
        display_name={"uk": "Слоти пам'яті", "en": "Memory slots"},
        data_type=DataType.QUANTITY,
        canonical_unit="slots",
        value_constraints={"min": 0, "max": 32},
        synonyms=(
            "memory slots",
            "dimm slots",
            "number of memory slots",
            "ram slots",
            "слоти пам'яті",
        ),
    ),
    CanonicalAttribute(
        attribute_key="max_memory",
        category_path=_MOTHERBOARD,
        display_name={"uk": "Макс. пам'ять", "en": "Max memory"},
        data_type=DataType.QUANTITY,
        canonical_unit="gb",
        allowed_units=("gb", "mb", "tb"),
        value_constraints={"min": 0, "max": 8192},
        synonyms=(
            "max memory",
            "maximum memory",
            "memory max",
            "max capacity",
            "максимум пам'яті",
        ),
    ),
    # --- Monitors ---------------------------------------------------------
    CanonicalAttribute(
        attribute_key="resolution",
        category_path=_MONITOR,
        display_name={"uk": "Роздільна здатність", "en": "Resolution"},
        data_type=DataType.TEXT,
        synonyms=(
            "resolution",
            "max resolution",
            "maximum resolution",
            "native resolution",
            "роздільна здатність",
        ),
    ),
    CanonicalAttribute(
        attribute_key="refresh_rate",
        category_path=_MONITOR,
        display_name={"uk": "Частота оновлення", "en": "Refresh rate"},
        data_type=DataType.QUANTITY,
        canonical_unit="hz",
        allowed_units=("hz", "khz"),
        value_constraints={"min": 0, "max": 1000},
        synonyms=(
            "refresh rate",
            "max refresh rate",
            "maximum refresh rate",
            "частота оновлення",
        ),
    ),
    CanonicalAttribute(
        attribute_key="panel_type",
        category_path=_MONITOR,
        display_name={"uk": "Тип матриці", "en": "Panel type"},
        data_type=DataType.TEXT,
        synonyms=("panel type", "panel", "matrix type", "тип матриці", "матриця"),
    ),
    CanonicalAttribute(
        attribute_key="response_time",
        category_path=_MONITOR,
        display_name={"uk": "Час відгуку", "en": "Response time"},
        data_type=DataType.QUANTITY,
        canonical_unit="ms",
        allowed_units=("ms", "s"),
        value_constraints={"min": 0, "max": 1000},
        synonyms=("response time", "gtg", "grey to grey", "час відгуку"),
    ),
    # --- Laptops ----------------------------------------------------------
    CanonicalAttribute(
        attribute_key="ram",
        category_path=_LAPTOP,
        display_name={"uk": "Оперативна пам'ять", "en": "RAM"},
        data_type=DataType.QUANTITY,
        canonical_unit="gb",
        allowed_units=("gb", "mb", "tb"),
        value_constraints={"min": 0, "max": 4096},
        synonyms=(
            "ram",
            "system memory",
            "installed memory",
            "installed ram",
            "оперативна пам'ять",
            "озп",
        ),
    ),
    CanonicalAttribute(
        attribute_key="storage",
        category_path=_LAPTOP,
        display_name={"uk": "Накопичувач", "en": "Storage"},
        data_type=DataType.QUANTITY,
        canonical_unit="gb",
        allowed_units=("gb", "mb", "tb"),
        value_constraints={"min": 0, "max": 1048576},
        synonyms=(
            "storage",
            "storage capacity",
            "ssd",
            "ssd capacity",
            "disk",
            "накопичувач",
        ),
    ),
    CanonicalAttribute(
        attribute_key="cpu_model",
        category_path=_LAPTOP,
        display_name={"uk": "Процесор", "en": "Processor"},
        data_type=DataType.TEXT,
        synonyms=("processor", "cpu", "cpu model", "processor model", "процесор"),
    ),
    CanonicalAttribute(
        attribute_key="gpu_model",
        category_path=_LAPTOP,
        display_name={"uk": "Відеокарта", "en": "Graphics"},
        data_type=DataType.TEXT,
        synonyms=(
            "graphics",
            "graphics card",
            "video card",
            "gpu model",
            "graphics processor",
            "відеокарта",
        ),
    ),
    # --- Graphics cards ---------------------------------------------------
    CanonicalAttribute(
        attribute_key="gpu_memory",
        category_path=_GPU,
        display_name={"uk": "Відеопам'ять", "en": "Video memory"},
        data_type=DataType.QUANTITY,
        canonical_unit="gb",
        allowed_units=("gb", "mb"),
        value_constraints={"min": 0, "max": 1024},
        synonyms=(
            "video memory",
            "graphics memory",
            "memory size",
            "vram",
            "відеопам'ять",
            "обсяг відеопам'яті",
        ),
    ),
    CanonicalAttribute(
        attribute_key="gpu_boost_clock",
        category_path=_GPU,
        display_name={"uk": "Boost-частота GPU", "en": "GPU boost clock"},
        data_type=DataType.QUANTITY,
        canonical_unit="mhz",
        allowed_units=("mhz", "ghz"),
        value_constraints={"min": 0, "max": 100000},
        synonyms=(
            "boost clock",
            "boost clock speed",
            "gpu boost clock",
            "game clock",
        ),
    ),
    CanonicalAttribute(
        attribute_key="gpu_cores",
        category_path=_GPU,
        display_name={"uk": "Ядра GPU", "en": "GPU cores"},
        data_type=DataType.QUANTITY,
        canonical_unit="cores",
        value_constraints={"min": 0, "max": 100000},
        synonyms=(
            "cuda cores",
            "stream processors",
            "shading units",
            "gpu cores",
        ),
    ),
    CanonicalAttribute(
        attribute_key="interface",
        category_path=_GPU,
        display_name={"uk": "Інтерфейс", "en": "Interface"},
        data_type=DataType.TEXT,
        synonyms=("interface", "bus interface", "pci express", "pcie", "інтерфейс"),
    ),
    # --- CPUs -------------------------------------------------------------
    CanonicalAttribute(
        attribute_key="cores",
        category_path=_CPU,
        display_name={"uk": "Кількість ядер", "en": "Cores"},
        data_type=DataType.QUANTITY,
        canonical_unit="cores",
        value_constraints={"min": 0, "max": 256},
        synonyms=(
            "cores",
            "total cores",
            "number of cores",
            "core count",
            "of cores",
            "кількість ядер",
            "ядра",
        ),
    ),
    CanonicalAttribute(
        attribute_key="threads",
        category_path=_CPU,
        display_name={"uk": "Кількість потоків", "en": "Threads"},
        data_type=DataType.QUANTITY,
        canonical_unit="threads",
        value_constraints={"min": 0, "max": 512},
        synonyms=(
            "threads",
            "total threads",
            "number of threads",
            "thread count",
            "of threads",
            "кількість потоків",
            "потоки",
        ),
    ),
    CanonicalAttribute(
        attribute_key="cpu_base_clock",
        category_path=_CPU,
        display_name={"uk": "Базова частота", "en": "Base clock"},
        data_type=DataType.QUANTITY,
        canonical_unit="ghz",
        allowed_units=("ghz", "mhz"),
        value_constraints={"min": 0, "max": 100},
        synonyms=(
            "base clock",
            "base frequency",
            "processor base frequency",
            "base clock speed",
            "базова частота",
        ),
    ),
    CanonicalAttribute(
        attribute_key="cpu_boost_clock",
        category_path=_CPU,
        display_name={"uk": "Turbo-частота", "en": "Max turbo frequency"},
        data_type=DataType.QUANTITY,
        canonical_unit="ghz",
        allowed_units=("ghz", "mhz"),
        value_constraints={"min": 0, "max": 100},
        synonyms=(
            "max turbo frequency",
            "maximum turbo frequency",
            "turbo frequency",
            "max turbo",
            "boost frequency",
            "турбо частота",
        ),
    ),
    CanonicalAttribute(
        attribute_key="cache",
        category_path=_CPU,
        display_name={"uk": "Кеш", "en": "Cache"},
        data_type=DataType.QUANTITY,
        canonical_unit="mb",
        allowed_units=("mb", "kb"),
        value_constraints={"min": 0, "max": 4096},
        synonyms=(
            "cache",
            "l3 cache",
            "smart cache",
            "intel smart cache",
            "кеш",
        ),
    ),
)

ONTOLOGY: dict[str, CanonicalAttribute] = {a.attribute_key: a for a in _ATTRIBUTES}


def get_attribute(attribute_key: str) -> CanonicalAttribute | None:
    return ONTOLOGY.get(attribute_key)
