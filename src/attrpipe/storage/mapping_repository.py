"""Confirmed attribute-mapping dictionary (docs/03 §2.1, §2.4).

Closes the HITL learning loop: a human-confirmed ``raw_attribute -> attribute_key``
mapping is stored here, and the deterministic dictionary mapper is seeded from
it, so the next time the same raw attribute appears it maps automatically. Manual
work is one-off per new pattern, not per occurrence.
"""

from typing import Any

import psycopg
from pydantic import BaseModel


class MappingEntry(BaseModel):
    raw_attribute: str
    attribute_key: str
    language: str
    category_path: list[str]
    confirmed_by: str


class MappingDictionaryRepository:
    def __init__(self, conn: psycopg.Connection[dict[str, Any]]) -> None:
        self._conn = conn

    def upsert(
        self,
        raw_attribute: str,
        attribute_key: str,
        *,
        language: str = "und",
        category_path: tuple[str, ...] = (),
        confirmed_by: str = "hitl",
    ) -> None:
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO mapping_dictionary"
                " (raw_attribute, language, category_path, attribute_key, confirmed_by)"
                " VALUES (%s,%s,%s,%s,%s)"
                " ON CONFLICT (raw_attribute, language, category_path) DO UPDATE SET"
                " attribute_key = EXCLUDED.attribute_key,"
                " confirmed_by = EXCLUDED.confirmed_by, confirmed_at = now()",
                (raw_attribute, language, list(category_path), attribute_key, confirmed_by),
            )

    def resolve(
        self,
        raw_attribute: str,
        *,
        language: str = "und",
        category_path: tuple[str, ...] = (),
    ) -> str | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT attribute_key FROM mapping_dictionary"
                " WHERE raw_attribute = %s AND language = %s AND category_path = %s",
                (raw_attribute, language, list(category_path)),
            )
            row = cur.fetchone()
            return str(row["attribute_key"]) if row is not None else None

    def all_learned(self) -> dict[str, str]:
        """All confirmed mappings as ``raw_attribute -> attribute_key`` for seeding the mapper."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT raw_attribute, attribute_key FROM mapping_dictionary ORDER BY confirmed_at"
            )
            return {str(row["raw_attribute"]): str(row["attribute_key"]) for row in cur.fetchall()}
