"""Product & exact fact-lookup routes — the primary precision path (docs/05 §3).

Deterministic reads from the Canonical Fact Store: no LLM, no guessing. A
missing fact is an explicit 404 (honest "unknown", CLAUDE.md §2.6), counted on
the ``refused`` route so precision can be monitored (docs/08).
"""

from fastapi import APIRouter, HTTPException

from attrpipe.api.deps import FactRepositoryDep, ProductRepositoryDep
from attrpipe.api.metrics import rag_route_total
from attrpipe.api.schemas import FactOut, ProductOut

router = APIRouter(prefix="/v1", tags=["products"])


@router.get("/products/{product_id}")
def get_product(product_id: str, products: ProductRepositoryDep) -> ProductOut:
    record = products.get(product_id)
    if record is None:
        raise HTTPException(status_code=404, detail="product not found")
    return ProductOut.from_record(record)


@router.get("/products/{product_id}/facts")
def get_product_facts(product_id: str, facts: FactRepositoryDep) -> list[FactOut]:
    effective = facts.get_effective_facts(product_id)
    return [FactOut.from_fact(fact) for fact in effective]


@router.get("/products/{product_id}/facts/{attribute_key}")
def get_product_fact(product_id: str, attribute_key: str, facts: FactRepositoryDep) -> FactOut:
    fact = facts.get_effective_fact(product_id, attribute_key)
    if fact is None:
        rag_route_total.labels(route="refused").inc()
        raise HTTPException(status_code=404, detail="fact not found")
    rag_route_total.labels(route="exact_lookup").inc()
    return FactOut.from_fact(fact)
