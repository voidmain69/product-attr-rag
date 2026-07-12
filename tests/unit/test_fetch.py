import hashlib

import httpx
import pytest

from attrpipe.fetch import (
    PerDomainRateLimiter,
    RobotsDisallowedError,
    RobotsPolicy,
    StaticFetcher,
    canonicalize_url,
)

HTML = "<html><body><h1>Acme Model X</h1></body></html>"


class TestCanonicalizeUrl:
    def test_strips_tracking_and_sorts_query(self) -> None:
        url = "https://Vendor.com/p/x?utm_source=fb&b=2&a=1&fbclid=xyz#frag"
        assert canonicalize_url(url) == "https://vendor.com/p/x?a=1&b=2"

    def test_adds_root_path_and_drops_fragment(self) -> None:
        assert canonicalize_url("https://vendor.com#top") == "https://vendor.com/"


class TestRobotsPolicy:
    def test_absent_robots_allows(self) -> None:
        policy = RobotsPolicy(None, "attrpipe")
        assert policy.is_allowed("https://vendor.com/anything") is True
        assert policy.crawl_delay() is None

    def test_disallow_rule(self) -> None:
        robots = "User-agent: *\nDisallow: /private\nCrawl-delay: 2"
        policy = RobotsPolicy(robots, "attrpipe")
        assert policy.is_allowed("https://vendor.com/private/x") is False
        assert policy.is_allowed("https://vendor.com/public/x") is True
        assert policy.crawl_delay() == 2.0


class TestRateLimiter:
    def test_spaces_requests_to_same_domain(self) -> None:
        clock_time = [100.0]
        slept: list[float] = []
        limiter = PerDomainRateLimiter(
            min_interval_s=1.5,
            clock=lambda: clock_time[0],
            sleep=slept.append,
        )
        limiter.acquire("vendor.com")  # first hit: no wait
        limiter.acquire("vendor.com")  # immediate second hit: must wait full interval
        assert slept == [1.5]

    def test_independent_domains_do_not_wait(self) -> None:
        slept: list[float] = []
        limiter = PerDomainRateLimiter(1.5, clock=lambda: 0.0, sleep=slept.append)
        limiter.acquire("a.com")
        limiter.acquire("b.com")
        assert slept == []


def make_fetcher(handler: httpx.MockTransport, robots: RobotsPolicy | None = None) -> StaticFetcher:
    client = httpx.Client(transport=handler)
    limiter = PerDomainRateLimiter(0.0, clock=lambda: 0.0, sleep=lambda _: None)
    return StaticFetcher(client, limiter, robots=robots)


class TestStaticFetcher:
    def test_fetch_builds_raw_artifact(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, text=HTML, headers={"content-type": "text/html"})
        )
        fetcher = make_fetcher(transport)
        artifact = fetcher.fetch("https://vendor.com/p/x?utm_source=fb")

        assert artifact.content == HTML
        assert artifact.canonical_url == "https://vendor.com/p/x"
        assert artifact.render_mode == "static_http"
        assert artifact.content_type == "text/html"
        expected_hash = hashlib.sha256(HTML.encode()).hexdigest()
        assert artifact.raw_artifact_id == f"raw/vendor.com/{expected_hash}"

    def test_robots_disallow_raises_before_request(self) -> None:
        called = {"hit": False}

        def handler(req: httpx.Request) -> httpx.Response:
            called["hit"] = True
            return httpx.Response(200, text=HTML)

        robots = RobotsPolicy("User-agent: *\nDisallow: /private", "attrpipe")
        fetcher = make_fetcher(httpx.MockTransport(handler), robots=robots)
        with pytest.raises(RobotsDisallowedError):
            fetcher.fetch("https://vendor.com/private/x")
        assert called["hit"] is False  # never hit the network

    def test_http_error_propagates(self) -> None:
        transport = httpx.MockTransport(lambda req: httpx.Response(404))
        fetcher = make_fetcher(transport)
        with pytest.raises(httpx.HTTPStatusError):
            fetcher.fetch("https://vendor.com/missing")

    def test_same_content_yields_stable_id(self) -> None:
        transport = httpx.MockTransport(lambda req: httpx.Response(200, text=HTML))
        fetcher = make_fetcher(transport)
        a = fetcher.fetch("https://vendor.com/p/x")
        b = fetcher.fetch("https://vendor.com/p/x")
        assert a.raw_artifact_id == b.raw_artifact_id  # content hash is deterministic
