"""Natural-language answer route (docs/05). Fact-first: deterministic exact
lookup with citation, honest "unknown" otherwise. Each answer records its route
on the RAG metric so precision is observable (docs/08)."""

from fastapi import APIRouter

from attrpipe.api.deps import AnswerServiceDep
from attrpipe.api.metrics import rag_route_total
from attrpipe.api.schemas import AnswerIn
from attrpipe.rag import AnswerResult

router = APIRouter(prefix="/v1", tags=["answer"])


@router.post("/answer")
def answer(body: AnswerIn, service: AnswerServiceDep) -> AnswerResult:
    result = service.answer(
        body.question,
        product_id=body.product_id,
        gtin=body.gtin,
        mpn=body.mpn,
        brand=body.brand,
        model=body.model,
    )
    rag_route_total.labels(route=result.route.value).inc()
    return result
