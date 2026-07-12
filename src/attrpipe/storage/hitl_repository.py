"""Human-in-the-loop moderation queues (docs/06 §4).

People handle only exceptions — new/ambiguous attribute mappings, value
anomalies, low-confidence or disputed facts, ambiguous product merges — not the
whole stream. Each resolution is a learning signal that reduces future manual
work (docs/03 §2.4). This repository is the queue store over ``hitl_queue``.
Enqueue is deduplicated so the same exception does not pile up.
"""

from typing import Any, Literal

import psycopg
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from attrpipe.storage.db import generate_id

HitlQueue = Literal[
    "attribute_mapping",
    "low_confidence_fact",
    "disputed_fact",
    "entity_resolution",
    "value_anomaly",
]


class HitlItem(BaseModel):
    item_id: str
    queue: HitlQueue
    payload: dict[str, Any]
    priority: int
    status: str


class HitlRepository:
    def __init__(self, conn: psycopg.Connection[dict[str, Any]]) -> None:
        self._conn = conn

    def enqueue(
        self,
        queue: HitlQueue,
        payload: dict[str, Any],
        *,
        priority: int = 100,
        dedup: str | None = None,
    ) -> str | None:
        """Add an item; if ``dedup`` matches an open item in this queue, skip it.

        Returns the new item_id, or None when deduplicated.
        """
        stored = {**payload, "_dedup": dedup} if dedup is not None else payload
        with self._conn.transaction(), self._conn.cursor() as cur:
            if dedup is not None:
                cur.execute(
                    "SELECT 1 FROM hitl_queue WHERE queue = %s AND status = 'open'"
                    " AND payload->>'_dedup' = %s",
                    (queue, dedup),
                )
                if cur.fetchone() is not None:
                    return None
            item_id = generate_id("hitl")
            cur.execute(
                "INSERT INTO hitl_queue (item_id, queue, payload, priority) VALUES (%s,%s,%s,%s)",
                (item_id, queue, Jsonb(stored), priority),
            )
            return item_id

    def list_open(self, queue: HitlQueue, limit: int = 50) -> list[HitlItem]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT item_id, queue, payload, priority, status FROM hitl_queue"
                " WHERE queue = %s AND status = 'open' ORDER BY priority, created_at LIMIT %s",
                (queue, limit),
            )
            return [HitlItem.model_validate(row) for row in cur.fetchall()]

    def count_open(self) -> dict[str, int]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT queue, count(*) AS n FROM hitl_queue WHERE status = 'open' GROUP BY queue"
            )
            return {str(row["queue"]): int(row["n"]) for row in cur.fetchall()}

    def resolve(
        self,
        item_id: str,
        resolution: dict[str, Any],
        *,
        resolved_by: str,
        status: Literal["resolved", "rejected"] = "resolved",
    ) -> bool:
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.execute(
                "UPDATE hitl_queue SET status = %s, resolved_at = now(), resolved_by = %s,"
                " resolution = %s WHERE item_id = %s AND status = 'open'",
                (status, resolved_by, Jsonb(resolution), item_id),
            )
            return cur.rowcount > 0
