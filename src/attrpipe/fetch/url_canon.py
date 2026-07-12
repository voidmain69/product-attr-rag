"""URL canonicalization (docs/01 §1).

Strips tracking parameters, lowercases scheme/host, sorts the query and drops
the fragment so the same page under different URLs deduplicates to one key.
"""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PREFIXES = ("utm_",)
_TRACKING_KEYS = frozenset({"gclid", "fbclid", "yclid", "mc_eid", "_ga", "ref", "ref_"})


def _is_tracking(key: str) -> bool:
    lowered = key.lower()
    return lowered in _TRACKING_KEYS or lowered.startswith(_TRACKING_PREFIXES)


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url)
    query = sorted(
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _is_tracking(k)
    )
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path or "/",
            urlencode(query),
            "",  # drop fragment
        )
    )
