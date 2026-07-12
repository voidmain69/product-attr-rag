"""Structured multi-product routes — filter & compare (docs/05 §6).

Where fact-first pays off: numeric filters and comparisons run as SQL over
normalized canonical facts, in canonical units, which vector search does poorly.
"""

from fastapi import APIRouter

from attrpipe.api.deps import FactRepositoryDep
from attrpipe.api.schemas import (
    CompareCell,
    CompareIn,
    CompareOut,
    CompareRow,
    FilterIn,
    FilterOut,
)
from attrpipe.storage import Constraint

router = APIRouter(prefix="/v1", tags=["queries"])


@router.post("/filter")
def filter_products(body: FilterIn, facts: FactRepositoryDep) -> FilterOut:
    constraints = [
        Constraint(attribute_key=c.attribute_key, op=c.op, value=c.value) for c in body.constraints
    ]
    product_ids = facts.filter_products(constraints, limit=body.limit)
    return FilterOut(product_ids=product_ids, count=len(product_ids))


@router.post("/compare")
def compare_products(body: CompareIn, facts: FactRepositoryDep) -> CompareOut:
    found = facts.compare(body.product_ids, body.attribute_keys)
    rows: dict[str, dict[str, CompareCell]] = {pid: {} for pid in body.product_ids}
    for fact in found:
        rows.setdefault(fact.product_id, {})[fact.attribute_key] = CompareCell(
            canonical_value=fact.canonical_value,
            canonical_unit=fact.canonical_unit,
            original_value=fact.original_value,
        )
    return CompareOut(
        attribute_keys=body.attribute_keys,
        rows=[CompareRow(product_id=pid, attributes=rows[pid]) for pid in body.product_ids],
    )
