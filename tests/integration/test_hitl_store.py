"""HITL queue integration tests (docs/09 §4). Require Postgres:
``python tools/dev.py up``. Excluded from default CI.
"""

import os
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from psycopg.rows import dict_row

from attrpipe.storage import HitlRepository

pytestmark = pytest.mark.integration


def _dsn() -> str:
    password = os.environ.get("POSTGRES_PASSWORD", "attrpipe-local")
    return f"postgresql://attrpipe:{password}@localhost:5432/attrpipe"


@pytest.fixture
def hitl() -> Iterator[tuple[HitlRepository, list[str]]]:
    try:
        conn = psycopg.connect(_dsn(), row_factory=dict_row, connect_timeout=3)
    except psycopg.OperationalError as exc:  # pragma: no cover
        pytest.skip(f"Postgres not available: {exc}")
    created: list[str] = []
    yield HitlRepository(conn), created
    with conn.transaction(), conn.cursor() as cur:
        for item_id in created:
            cur.execute("DELETE FROM hitl_queue WHERE item_id = %s", (item_id,))
    conn.close()


def _payload(attr: str) -> dict[str, Any]:
    return {"raw_attribute": attr, "source_url": "https://v/x"}


class TestHitlQueue:
    def test_enqueue_and_list(self, hitl: tuple[HitlRepository, list[str]]) -> None:
        repo, created = hitl
        item_id = repo.enqueue("attribute_mapping", _payload("Вес нетто"), dedup="Вес нетто")
        assert item_id is not None
        created.append(item_id)

        items = [i for i in repo.list_open("attribute_mapping") if i.item_id == item_id]
        assert len(items) == 1
        assert items[0].payload["raw_attribute"] == "Вес нетто"
        assert items[0].status == "open"

    def test_dedup_skips_duplicate(self, hitl: tuple[HitlRepository, list[str]]) -> None:
        repo, created = hitl
        first = repo.enqueue("attribute_mapping", _payload("torque"), dedup="torque")
        assert first is not None
        created.append(first)
        second = repo.enqueue("attribute_mapping", _payload("torque"), dedup="torque")
        assert second is None  # deduplicated while the first is still open

    def test_resolve_closes_item(self, hitl: tuple[HitlRepository, list[str]]) -> None:
        repo, created = hitl
        item_id = repo.enqueue("value_anomaly", _payload("weight"), dedup="weight:9e9")
        assert item_id is not None
        created.append(item_id)

        ok = repo.resolve(item_id, {"decision": "reject"}, resolved_by="tester")
        assert ok is True
        assert all(i.item_id != item_id for i in repo.list_open("value_anomaly"))
        # resolving again is a no-op
        assert repo.resolve(item_id, {}, resolved_by="tester") is False

    def test_count_open(self, hitl: tuple[HitlRepository, list[str]]) -> None:
        repo, created = hitl
        item_id = repo.enqueue("disputed_fact", _payload("weight"), dedup="disp-1")
        assert item_id is not None
        created.append(item_id)
        counts = repo.count_open()
        assert counts.get("disputed_fact", 0) >= 1
