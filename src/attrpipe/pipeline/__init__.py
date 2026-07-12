"""Ingestion orchestration — wires the layers into one end-to-end flow.

`IngestPipeline.ingest(url)` runs fetch -> Raw Store -> extract -> normalize ->
persist, honoring the cost cascade and provenance of the underlying layers.
This is the synchronous composition; a queue-driven version (docs/07 §2) is a
later step.
"""

from attrpipe.pipeline.ingest import IngestPipeline, IngestResult

__all__ = ["IngestPipeline", "IngestResult"]
