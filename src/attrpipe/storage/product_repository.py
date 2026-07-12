"""Product entity resolution & persistence (docs/03 §4, docs/04 §2).

Resolves the same product across sources to a single ``product_id`` using the
reliability ladder GTIN > MPN+brand > brand+model, creating a new product only
when no match is found. Every resolving source URL is accumulated on the
product so facts from different pages attach to one entity.
"""

from typing import Any

import psycopg
from pydantic import BaseModel

from attrpipe.storage.db import generate_id


class ProductRef(BaseModel):
    """Identity signals for one product, gathered during extraction."""

    brand: str
    model: str
    gtin: str | None = None
    mpn: str | None = None
    category_path: tuple[str, ...] = ()
    canonical_title: str | None = None
    source_url: str | None = None


class ProductRecord(BaseModel):
    """A persisted product entity (read model)."""

    product_id: str
    brand: str
    model: str
    category_path: list[str]
    gtin: str | None = None
    mpn: str | None = None
    canonical_title: str | None = None
    source_urls: list[str]


class ProductRepository:
    def __init__(self, conn: psycopg.Connection[dict[str, Any]]) -> None:
        self._conn = conn

    def resolve_or_create(self, ref: ProductRef) -> str:
        with self._conn.transaction(), self._conn.cursor() as cur:
            product_id = self._find(cur, ref)
            if product_id is not None:
                if ref.source_url:
                    cur.execute(
                        "UPDATE products SET source_urls = ("
                        "  SELECT array(SELECT DISTINCT unnest(source_urls || %s::text[]))"
                        "), updated_at = now() WHERE product_id = %s",
                        ([ref.source_url], product_id),
                    )
                return product_id

            new_id = generate_id("prd")
            cur.execute(
                "INSERT INTO products (product_id, brand, model, category_path, gtin, mpn,"
                " canonical_title, source_urls) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    new_id,
                    ref.brand,
                    ref.model,
                    list(ref.category_path),
                    ref.gtin,
                    ref.mpn,
                    ref.canonical_title,
                    [ref.source_url] if ref.source_url else [],
                ),
            )
            return new_id

    def get(self, product_id: str) -> ProductRecord | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT product_id, brand, model, category_path, gtin, mpn,"
                " canonical_title, source_urls FROM products WHERE product_id = %s",
                (product_id,),
            )
            row = cur.fetchone()
            return ProductRecord.model_validate(row) if row is not None else None

    def resolve(
        self,
        *,
        gtin: str | None = None,
        mpn: str | None = None,
        brand: str | None = None,
        model: str | None = None,
    ) -> str | None:
        """Read-only entity resolution by GTIN > MPN+brand > brand+model, or None."""
        with self._conn.cursor() as cur:
            return self._resolve(cur, gtin=gtin, mpn=mpn, brand=brand, model=model)

    def _find(self, cur: psycopg.Cursor[dict[str, Any]], ref: ProductRef) -> str | None:
        return self._resolve(cur, gtin=ref.gtin, mpn=ref.mpn, brand=ref.brand, model=ref.model)

    def _resolve(
        self,
        cur: psycopg.Cursor[dict[str, Any]],
        *,
        gtin: str | None,
        mpn: str | None,
        brand: str | None,
        model: str | None,
    ) -> str | None:
        if gtin:
            cur.execute("SELECT product_id FROM products WHERE gtin = %s", (gtin,))
            row = cur.fetchone()
            if row is not None:
                return str(row["product_id"])
        if mpn and brand:
            cur.execute(
                "SELECT product_id FROM products WHERE mpn = %s AND brand = %s",
                (mpn, brand),
            )
            row = cur.fetchone()
            if row is not None:
                return str(row["product_id"])
        if brand and model:
            cur.execute(
                "SELECT product_id FROM products WHERE brand = %s AND lower(model) = lower(%s)",
                (brand, model),
            )
            row = cur.fetchone()
            if row is not None:
                return str(row["product_id"])
        return None
