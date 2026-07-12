"""FastAPI dependencies — per-request fact-store connection and repositories.

Tests override ``get_fact_repository`` / ``get_product_repository`` with fakes,
so the API can be unit-tested without a database.
"""

from collections.abc import Iterator
from typing import Annotated, Any

import psycopg
from fastapi import Depends

from attrpipe.storage import FactRepository, ProductRepository, connect


def get_connection() -> Iterator[psycopg.Connection[dict[str, Any]]]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


ConnectionDep = Annotated[psycopg.Connection[dict[str, Any]], Depends(get_connection)]


def get_fact_repository(conn: ConnectionDep) -> FactRepository:
    return FactRepository(conn)


def get_product_repository(conn: ConnectionDep) -> ProductRepository:
    return ProductRepository(conn)


FactRepositoryDep = Annotated[FactRepository, Depends(get_fact_repository)]
ProductRepositoryDep = Annotated[ProductRepository, Depends(get_product_repository)]
