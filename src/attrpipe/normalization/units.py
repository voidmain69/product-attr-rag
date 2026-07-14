"""Value & unit normalization for quantities (docs/03 §3.1, §3.6).

Parses a raw quantity ("2,3 кг", "2.3kg", "2300 g") and converts it to the
attribute's canonical unit. Locale decimal comma is handled explicitly.
Returns ``None`` when the value cannot be parsed as a number — the caller
decides what to do with an unparseable candidate (e.g. drop or route to HITL).
"""

import re

# Conversion factor of each unit to its dimension's base unit.
# Base units: mass=gram, length=millimetre, time=hour, frequency=hertz,
# power=watt, data=megabyte, and unitless counts (kept as their own dimensions
# so a count never converts into a physical quantity).
_UNIT_FACTORS: dict[str, tuple[str, float]] = {
    "g": ("mass", 1.0),
    "kg": ("mass", 1000.0),
    "mg": ("mass", 0.001),
    "oz": ("mass", 28.349523125),
    "lb": ("mass", 453.59237),
    "mm": ("length", 1.0),
    "cm": ("length", 10.0),
    "m": ("length", 1000.0),
    "in": ("length", 25.4),
    "h": ("time", 1.0),
    "hr": ("time", 1.0),
    "min": ("time", 1.0 / 60.0),
    "s": ("time", 1.0 / 3600.0),
    "ms": ("time", 1.0 / 3_600_000.0),
    "hz": ("frequency", 1.0),
    "khz": ("frequency", 1_000.0),
    "mhz": ("frequency", 1_000_000.0),
    "ghz": ("frequency", 1_000_000_000.0),
    "w": ("power", 1.0),
    "kw": ("power", 1000.0),
    "mb": ("data", 1.0),
    "gb": ("data", 1024.0),
    "tb": ("data", 1_048_576.0),
    # Unitless counts — each its own dimension so it never cross-converts.
    "cores": ("count_cores", 1.0),
    "threads": ("count_threads", 1.0),
    "slots": ("count_slots", 1.0),
}

# Spelled-out / plural unit spellings (common in LLM prose) mapped to canonical symbols.
_UNIT_ALIASES: dict[str, str] = {
    "gram": "g",
    "grams": "g",
    "gramme": "g",
    "grammes": "g",
    "kilogram": "kg",
    "kilograms": "kg",
    "kilogramme": "kg",
    "kilogrammes": "kg",
    "milligram": "mg",
    "milligrams": "mg",
    "ounce": "oz",
    "ounces": "oz",
    "pound": "lb",
    "pounds": "lb",
    "millimeter": "mm",
    "millimeters": "mm",
    "millimetre": "mm",
    "millimetres": "mm",
    "centimeter": "cm",
    "centimeters": "cm",
    "centimetre": "cm",
    "centimetres": "cm",
    "meter": "m",
    "meters": "m",
    "metre": "m",
    "metres": "m",
    "hour": "h",
    "hours": "h",
    "hrs": "h",
    "minute": "min",
    "minutes": "min",
    "mins": "min",
    "second": "s",
    "seconds": "s",
    "secs": "s",
    "sec": "s",
    "millisecond": "ms",
    "milliseconds": "ms",
    "msec": "ms",
    "inch": "in",
    "inches": "in",
    '"': "in",
    "″": "in",
    "hertz": "hz",
    "kilohertz": "khz",
    "megahertz": "mhz",
    "gigahertz": "ghz",
    "watt": "w",
    "watts": "w",
    "kilowatt": "kw",
    "kilowatts": "kw",
    "megabyte": "mb",
    "megabytes": "mb",
    "gigabyte": "gb",
    "gigabytes": "gb",
    "terabyte": "tb",
    "terabytes": "tb",
    "core": "cores",
    "thread": "threads",
    "slot": "slots",
}

_NUMBER_RE = re.compile(r"[-+]?\d*[.,]?\d+")


def parse_number(raw: str) -> float | None:
    """Extract the first number from ``raw``, honoring a decimal comma."""
    match = _NUMBER_RE.search(raw.strip())
    if match is None:
        return None
    token = match.group().replace(",", ".")
    try:
        return float(token)
    except ValueError:
        return None


def normalize_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    cleaned = unit.strip().lower().rstrip(".")
    if not cleaned:
        return None
    return _UNIT_ALIASES.get(cleaned, cleaned)


def convert(value: float, from_unit: str | None, canonical_unit: str) -> float | None:
    """Convert ``value`` from ``from_unit`` to ``canonical_unit`` within one dimension.

    A missing ``from_unit`` is assumed to already be the canonical unit.
    Returns ``None`` on unknown units or a cross-dimension mismatch.
    """
    src = normalize_unit(from_unit) or canonical_unit
    dst = normalize_unit(canonical_unit)
    if dst is None:
        return None
    if src == dst:
        return round(value, 6)
    if src not in _UNIT_FACTORS or dst not in _UNIT_FACTORS:
        return None
    src_dim, src_factor = _UNIT_FACTORS[src]
    dst_dim, dst_factor = _UNIT_FACTORS[dst]
    if src_dim != dst_dim:
        return None
    return round(value * src_factor / dst_factor, 6)


def normalize_quantity(raw_value: str, raw_unit: str | None, canonical_unit: str) -> float | None:
    """Parse and convert a raw quantity to the canonical unit, or ``None``."""
    number = parse_number(raw_value)
    if number is None:
        return None
    return convert(number, raw_unit, canonical_unit)
