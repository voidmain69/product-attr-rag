"""Static HTTP fetcher — the cheap, default fetch path (docs/01 §3.1).

Fetches a URL with browser-like headers over an injected httpx client,
honoring robots.txt and per-domain rate limits, and returns a RawArtifact with
full fetch provenance (content hash, canonical URL, timestamp). Headless
rendering (docs/01 §3.2) is a separate, escalated path.

The httpx client is injected so tests drive it via a MockTransport and never
touch a live site (CLAUDE.md §6).
"""

import hashlib
from datetime import UTC, datetime

import httpx

from attrpipe.core.logging import get_logger
from attrpipe.domain import RawArtifact
from attrpipe.fetch.politeness import PerDomainRateLimiter, RobotsPolicy
from attrpipe.fetch.url_canon import canonicalize_url

logger = get_logger(__name__)

DEFAULT_USER_AGENT = "attrpipe/0.1 (+https://github.com/voidmain69/product-attr-rag)"
_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en,uk;q=0.8,ru;q=0.6",
}


class RobotsDisallowedError(Exception):
    """Raised when robots.txt forbids fetching a URL (docs/01 §5)."""

    def __init__(self, url: str) -> None:
        super().__init__(f"robots.txt disallows fetching {url}")
        self.url = url


class StaticFetcher:
    def __init__(
        self,
        client: httpx.Client,
        rate_limiter: PerDomainRateLimiter,
        robots: RobotsPolicy | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self._client = client
        self._rate_limiter = rate_limiter
        self._robots = robots
        self._headers = {**_HEADERS, "User-Agent": user_agent}

    def fetch(self, url: str) -> RawArtifact:
        if self._robots is not None and not self._robots.is_allowed(url):
            logger.info("fetch_robots_disallowed", url=url)
            raise RobotsDisallowedError(url)

        domain = httpx.URL(url).host
        crawl_delay = self._robots.crawl_delay() if self._robots is not None else None
        self._rate_limiter.acquire(domain, crawl_delay)

        response = self._client.get(url, headers=self._headers, follow_redirects=True)
        response.raise_for_status()

        content_hash = hashlib.sha256(response.content).hexdigest()
        canonical = canonicalize_url(str(response.url))
        logger.info(
            "fetch_ok",
            url=url,
            http_status=response.status_code,
            content_hash=content_hash,
        )
        return RawArtifact(
            raw_artifact_id=f"raw/{domain}/{content_hash}",
            url=url,
            canonical_url=canonical,
            content=response.text,
            content_type=response.headers.get("content-type", "text/html"),
            fetched_at=datetime.now(UTC),
            render_mode="static_http",
        )
