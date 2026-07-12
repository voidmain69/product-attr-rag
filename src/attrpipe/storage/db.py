"""Database access helpers for the Canonical Fact Store (docs/04).

Thin wrapper over psycopg: a connection factory bound to app settings and an
id generator. Repositories take a connection so callers control transactions
and tests can inject their own.
"""

from typing import Any
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from attrpipe.core.config import get_settings


def connect() -> psycopg.Connection[dict[str, Any]]:
    """Open a fact-store connection using app settings (dict rows)."""
    return psycopg.connect(get_settings().postgres_dsn, row_factory=dict_row)


def generate_id(prefix: str) -> str:
    """Generate a prefixed, sortable-enough identifier, e.g. ``fct_<hex>``."""
    return f"{prefix}_{uuid4().hex[:26]}"
