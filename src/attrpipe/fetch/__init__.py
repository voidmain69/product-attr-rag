"""Fetch — static/headless fetcher pool, politeness, Raw Store (docs/01).

Rules baked into this layer:
- static-first; headless only when embedded/API data is unavailable;
- per-domain token buckets, robots.txt and Crawl-delay respected;
- every response lands in the Raw Store with full fetch provenance
  (url, fetched_at, http_status, content_hash, render_mode, detected_engine).
"""

from attrpipe.fetch.politeness import PerDomainRateLimiter, RobotsPolicy
from attrpipe.fetch.static_fetcher import (
    DEFAULT_USER_AGENT,
    RobotsDisallowedError,
    StaticFetcher,
)
from attrpipe.fetch.url_canon import canonicalize_url

__all__ = [
    "DEFAULT_USER_AGENT",
    "PerDomainRateLimiter",
    "RobotsDisallowedError",
    "RobotsPolicy",
    "StaticFetcher",
    "canonicalize_url",
]
