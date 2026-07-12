"""FastAPI dependencies — per-request fact-store connection and repositories.

Tests override ``get_fact_repository`` / ``get_product_repository`` with fakes,
so the API can be unit-tested without a database.
"""

from collections.abc import Iterator
from typing import Annotated, Any

import psycopg
from fastapi import Depends

from attrpipe.rag import AnswerService
from attrpipe.storage import (
    ChunkRepository,
    FactRepository,
    HashingEmbedder,
    HitlRepository,
    MappingDictionaryRepository,
    ProductRepository,
    connect,
)


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


def get_answer_service(conn: ConnectionDep) -> AnswerService:
    retriever = ChunkRepository(conn, HashingEmbedder())
    return AnswerService(ProductRepository(conn), FactRepository(conn), retriever=retriever)


def get_hitl_repository(conn: ConnectionDep) -> HitlRepository:
    return HitlRepository(conn)


def get_mapping_repository(conn: ConnectionDep) -> MappingDictionaryRepository:
    return MappingDictionaryRepository(conn)


FactRepositoryDep = Annotated[FactRepository, Depends(get_fact_repository)]
ProductRepositoryDep = Annotated[ProductRepository, Depends(get_product_repository)]
AnswerServiceDep = Annotated[AnswerService, Depends(get_answer_service)]
HitlRepositoryDep = Annotated[HitlRepository, Depends(get_hitl_repository)]
MappingRepositoryDep = Annotated[MappingDictionaryRepository, Depends(get_mapping_repository)]
