"""FastAPI application for the answering service (docs/05).

Run locally:  python tools/dev.py serve   (or: uvicorn attrpipe.api.app:app)
Needs the fact store reachable — set POSTGRES_PASSWORD (or .env) to match the
docker-compose stack, then ``python tools/dev.py up``.
"""

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from attrpipe import __version__
from attrpipe.api.routes import attributes, products
from attrpipe.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging("attrpipe-api")
    app = FastAPI(
        title="attrpipe",
        version=__version__,
        summary="Fact-first product-attribute answering service",
    )
    app.include_router(products.router)
    app.include_router(attributes.router)

    @app.get("/healthz", tags=["ops"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics", tags=["ops"])
    def metrics() -> PlainTextResponse:
        return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
