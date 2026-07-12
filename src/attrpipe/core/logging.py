"""Structured JSON logging with correlation IDs.

Standard (docs/08-telemetry-standards.md): every log line is JSON with
`event`, `level`, `timestamp`, `service`, and — where applicable —
`trace_id` / `artifact_id` / `product_id` so a unit of work can be followed
end-to-end across pipeline layers.
"""

import logging
import sys

import structlog

from attrpipe.core.config import get_settings


def configure_logging(service: str | None = None) -> None:
    settings = get_settings()
    # Logs carry non-ASCII (multilingual raw attributes). Force UTF-8 on stdout so a
    # legacy console encoding (e.g. Windows cp1252) cannot crash a log write.
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="backslashreplace")
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )
    structlog.contextvars.bind_contextvars(service=service or settings.otel_service_name)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]
