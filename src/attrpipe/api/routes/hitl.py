"""Human-in-the-loop moderation routes (docs/06 §4).

Surfaces the exception queues so a human resolves only what the deterministic
pipeline could not: unmapped attributes, value anomalies, disputes. Queue depth
is published to Prometheus (docs/08 §5 HitlBacklog alert).
"""

from typing import Any, get_args

from fastapi import APIRouter, HTTPException

from attrpipe.api.deps import HitlRepositoryDep, MappingRepositoryDep
from attrpipe.api.metrics import hitl_queue_depth
from attrpipe.storage import HitlItem, HitlQueue

router = APIRouter(prefix="/v1/hitl", tags=["hitl"])

_QUEUES: tuple[str, ...] = get_args(HitlQueue)


def _validate(queue: str) -> HitlQueue:
    if queue not in _QUEUES:
        raise HTTPException(status_code=404, detail=f"unknown queue; expected one of {_QUEUES}")
    return queue  # type: ignore[return-value]


@router.get("")
def queue_counts(hitl: HitlRepositoryDep) -> dict[str, int]:
    counts = hitl.count_open()
    for queue in _QUEUES:
        hitl_queue_depth.labels(queue=queue).set(counts.get(queue, 0))
    return {queue: counts.get(queue, 0) for queue in _QUEUES}


@router.get("/{queue}")
def list_queue(queue: str, hitl: HitlRepositoryDep, limit: int = 50) -> list[HitlItem]:
    return hitl.list_open(_validate(queue), limit=limit)


@router.post("/{item_id}/resolve")
def resolve_item(
    item_id: str,
    body: dict[str, Any],
    hitl: HitlRepositoryDep,
    mappings: MappingRepositoryDep,
) -> dict[str, Any]:
    item = hitl.get(item_id)
    if item is None or item.status != "open":
        raise HTTPException(status_code=404, detail="item not found or already resolved")
    resolution = body.get("resolution") or {}
    resolved_by = body.get("resolved_by", "api")
    hitl.resolve(item_id, resolution, resolved_by=resolved_by)

    # Close the learning loop: a confirmed attribute mapping is written to the
    # dictionary so the same raw attribute maps automatically next time (docs/03 §2.4).
    learned: dict[str, str] | None = None
    attribute_key = resolution.get("attribute_key") if isinstance(resolution, dict) else None
    raw_attribute = item.payload.get("raw_attribute")
    if item.queue == "attribute_mapping" and attribute_key and isinstance(raw_attribute, str):
        mappings.upsert(raw_attribute, attribute_key, confirmed_by=resolved_by)
        learned = {"raw_attribute": raw_attribute, "attribute_key": attribute_key}

    return {"status": "resolved", "learned": learned}
