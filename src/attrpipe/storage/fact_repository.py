"""Canonical Fact Store repository — append-only versioning (docs/04 §3).

Facts are never updated in place. Writing a new value for
``(product_id, attribute_key)`` supersedes the current effective fact (sets its
``superseded_by`` and clears ``effective``) and inserts a new row. Re-writing an
identical fact is a no-op, which keeps reprocessing the same artifact idempotent
(CLAUDE.md §2.3). Current state is ``effective = true AND superseded_by IS NULL``.
"""

from typing import Any, Literal

import psycopg
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from attrpipe.domain import CanonicalFact, Provenance
from attrpipe.domain.facts import DataType
from attrpipe.storage.db import generate_id

FilterOp = Literal["eq", "ne", "lt", "lte", "gt", "gte"]
_SQL_OPS: dict[str, str] = {
    "eq": "=",
    "ne": "<>",
    "lt": "<",
    "lte": "<=",
    "gt": ">",
    "gte": ">=",
}
_NUMERIC_OPS = frozenset({"lt", "lte", "gt", "gte"})


class Constraint(BaseModel):
    attribute_key: str
    op: FilterOp = "eq"
    value: str | float | bool


class FactRepository:
    def __init__(self, conn: psycopg.Connection[dict[str, Any]]) -> None:
        self._conn = conn

    def upsert(self, fact: CanonicalFact) -> str:
        """Insert ``fact`` as a new version, superseding the current one; return fact_id."""
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.execute(
                "SELECT fact_id, canonical_value, canonical_unit, provenance FROM facts"
                " WHERE product_id = %s AND attribute_key = %s"
                " AND effective AND superseded_by IS NULL FOR UPDATE",
                (fact.product_id, fact.attribute_key),
            )
            current = cur.fetchone()
            if current is not None and _unchanged(current, fact):
                return str(current["fact_id"])

            new_id = generate_id("fct")
            cur.execute(
                "INSERT INTO facts (fact_id, product_id, attribute_key, ontology_version,"
                " data_type, canonical_value, canonical_unit, original_value, effective,"
                " disputed, confidence, provenance, valid_from)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,TRUE,%s,%s,%s,%s)",
                (
                    new_id,
                    fact.product_id,
                    fact.attribute_key,
                    fact.ontology_version,
                    fact.data_type.value,
                    Jsonb(fact.canonical_value),
                    fact.canonical_unit,
                    fact.original_value,
                    fact.disputed,
                    fact.confidence,
                    Jsonb(fact.provenance.model_dump(mode="json")),
                    fact.valid_from,
                ),
            )
            if current is not None:
                cur.execute(
                    "UPDATE facts SET effective = FALSE, superseded_by = %s WHERE fact_id = %s",
                    (new_id, current["fact_id"]),
                )
            return new_id

    def get_effective_facts(self, product_id: str) -> list[CanonicalFact]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM facts WHERE product_id = %s AND effective"
                " AND superseded_by IS NULL ORDER BY attribute_key",
                (product_id,),
            )
            return [_row_to_fact(row) for row in cur.fetchall()]

    def get_effective_fact(self, product_id: str, attribute_key: str) -> CanonicalFact | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM facts WHERE product_id = %s AND attribute_key = %s"
                " AND effective AND superseded_by IS NULL",
                (product_id, attribute_key),
            )
            row = cur.fetchone()
            return _row_to_fact(row) if row is not None else None

    def filter_products(self, constraints: list[Constraint], limit: int = 100) -> list[str]:
        """Return product_ids whose effective facts satisfy ALL constraints (docs/05 §6).

        Numeric comparisons run on the canonical (normalized) value, so filters
        like ``net_weight < 300`` are correct across source units.
        """
        if not constraints:
            return []
        clauses: list[str] = []
        params: list[Any] = []
        for constraint in constraints:
            sql_op = _SQL_OPS[constraint.op]
            if constraint.op in _NUMERIC_OPS:
                condition = f"(f.canonical_value #>> '{{}}')::numeric {sql_op} %s::numeric"
                value: Any = float(constraint.value)
            else:
                condition = f"(f.canonical_value #>> '{{}}') {sql_op} %s"
                value = str(constraint.value)
            clauses.append(
                "EXISTS (SELECT 1 FROM facts f WHERE f.product_id = p.product_id"
                " AND f.attribute_key = %s AND f.effective AND f.superseded_by IS NULL"
                f" AND {condition})"
            )
            params.extend((constraint.attribute_key, value))
        params.append(limit)
        sql = (
            "SELECT p.product_id FROM products p WHERE "
            + " AND ".join(clauses)
            + " ORDER BY p.product_id LIMIT %s"
        )
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            return [str(row["product_id"]) for row in cur.fetchall()]

    def compare(self, product_ids: list[str], attribute_keys: list[str]) -> list[CanonicalFact]:
        """Effective facts for the given products and attributes, for a comparison table."""
        if not product_ids or not attribute_keys:
            return []
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM facts WHERE product_id = ANY(%s) AND attribute_key = ANY(%s)"
                " AND effective AND superseded_by IS NULL"
                " ORDER BY product_id, attribute_key",
                (product_ids, attribute_keys),
            )
            return [_row_to_fact(row) for row in cur.fetchall()]


def _unchanged(current: dict[str, Any], fact: CanonicalFact) -> bool:
    provenance = current["provenance"]
    return bool(
        current["canonical_value"] == fact.canonical_value
        and current["canonical_unit"] == fact.canonical_unit
        and provenance.get("source_url") == fact.provenance.source_url
        and provenance.get("source_span") == fact.provenance.source_span
    )


def _row_to_fact(row: dict[str, Any]) -> CanonicalFact:
    return CanonicalFact(
        product_id=row["product_id"],
        attribute_key=row["attribute_key"],
        ontology_version=row["ontology_version"],
        data_type=DataType(row["data_type"]),
        canonical_value=row["canonical_value"],
        canonical_unit=row["canonical_unit"],
        original_value=row["original_value"],
        effective=row["effective"],
        disputed=row["disputed"],
        confidence=row["confidence"],
        provenance=Provenance.model_validate(row["provenance"]),
        valid_from=row["valid_from"],
        superseded_by=row["superseded_by"],
    )
