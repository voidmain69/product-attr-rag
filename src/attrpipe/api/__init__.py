"""HTTP answering service (docs/05).

Exposes exact fact-lookup over the Canonical Fact Store plus the attribute
ontology, with liveness and Prometheus metrics endpoints. The app is built by
``create_app()`` and also exported as ``app`` for ``uvicorn attrpipe.api.app:app``.
"""

from attrpipe.api.app import app, create_app

__all__ = ["app", "create_app"]
