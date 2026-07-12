"""Raw artifact model — the fetch -> extraction contract (docs/01 §7).

A RawArtifact is what the fetcher pool writes to the Raw Store: the decoded
response body plus fetch provenance. Extraction reads exclusively from these,
never from live sites, which is what makes the pipeline idempotent (docs/00).
"""

from datetime import datetime

from pydantic import BaseModel


class RawArtifact(BaseModel):
    raw_artifact_id: str  # Raw Store key, e.g. "s3://raw-artifacts/vendor.com/<hash>.html"
    url: str
    canonical_url: str | None = None
    content: str  # decoded text body (HTML / JSON)
    content_type: str = "text/html"
    fetched_at: datetime
    detected_engine: str | None = None
    render_mode: str = "static_http"

    @property
    def source_url(self) -> str:
        """URL to attribute facts to — canonical when known, else the fetched URL."""
        return self.canonical_url or self.url
