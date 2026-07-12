"""Mapping dictionary + learning-loop closure (docs/03 §2.4, docs/09 §4).
Requires Postgres: ``python tools/dev.py up``. Excluded from default CI.
"""

import os
from collections.abc import Iterator

import psycopg
import pytest
from psycopg.rows import dict_row

from attrpipe.normalization import DictionaryAttributeMapper
from attrpipe.storage import HitlRepository, MappingDictionaryRepository

pytestmark = pytest.mark.integration

NOVEL = "Загальна маса виробу"  # absent from ontology synonyms


def _dsn() -> str:
    password = os.environ.get("POSTGRES_PASSWORD", "attrpipe-local")
    return f"postgresql://attrpipe:{password}@localhost:5432/attrpipe"


@pytest.fixture
def repos() -> Iterator[tuple[MappingDictionaryRepository, HitlRepository]]:
    try:
        conn = psycopg.connect(_dsn(), row_factory=dict_row, connect_timeout=3)
    except psycopg.OperationalError as exc:  # pragma: no cover
        pytest.skip(f"Postgres not available: {exc}")
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM mapping_dictionary WHERE raw_attribute = %s", (NOVEL,))
    yield MappingDictionaryRepository(conn), HitlRepository(conn)
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM mapping_dictionary WHERE raw_attribute = %s", (NOVEL,))
    conn.close()


class TestMappingDictionary:
    def test_upsert_and_resolve(
        self, repos: tuple[MappingDictionaryRepository, HitlRepository]
    ) -> None:
        mappings, _ = repos
        mappings.upsert(NOVEL, "net_weight", confirmed_by="tester")
        assert mappings.resolve(NOVEL) == "net_weight"

    def test_upsert_is_idempotent_and_updatable(
        self, repos: tuple[MappingDictionaryRepository, HitlRepository]
    ) -> None:
        mappings, _ = repos
        mappings.upsert(NOVEL, "net_weight", confirmed_by="a")
        mappings.upsert(NOVEL, "battery_life", confirmed_by="b")  # correction
        assert mappings.resolve(NOVEL) == "battery_life"

    def test_learning_loop_closure(
        self, repos: tuple[MappingDictionaryRepository, HitlRepository]
    ) -> None:
        mappings, _ = repos

        # 1) before any confirmation, the novel label is unmapped
        before = DictionaryAttributeMapper(learned=mappings.all_learned())
        assert before.map(NOVEL) is None

        # 2) a human confirms the mapping (what the resolve route does)
        mappings.upsert(NOVEL, "net_weight", confirmed_by="moderator")

        # 3) a mapper seeded from the dictionary now maps it automatically
        after = DictionaryAttributeMapper(learned=mappings.all_learned())
        assert after.map(NOVEL) == "net_weight"
