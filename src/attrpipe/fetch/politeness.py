"""Politeness — robots.txt and per-domain rate limiting (docs/01 §4, §6).

Mandatory, not optional (CLAUDE.md §2.5). RobotsPolicy answers "may we fetch
this URL / what Crawl-delay applies"; PerDomainRateLimiter spaces requests to
one domain. Both take injectable clock/sleep so behaviour is deterministic in
tests.
"""

import time
from collections.abc import Callable
from urllib.robotparser import RobotFileParser


class RobotsPolicy:
    """Wraps a parsed robots.txt. Absent robots.txt means "allow"."""

    def __init__(self, robots_txt: str | None, user_agent: str) -> None:
        self._user_agent = user_agent
        if robots_txt is None:
            self._parser: RobotFileParser | None = None
        else:
            self._parser = RobotFileParser()
            self._parser.parse(robots_txt.splitlines())

    def is_allowed(self, url: str) -> bool:
        if self._parser is None:
            return True
        return self._parser.can_fetch(self._user_agent, url)

    def crawl_delay(self) -> float | None:
        if self._parser is None:
            return None
        delay = self._parser.crawl_delay(self._user_agent)
        return float(delay) if delay is not None else None


class PerDomainRateLimiter:
    """Token-free min-interval limiter: enforces a gap between hits to a domain."""

    def __init__(
        self,
        min_interval_s: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._min_interval = min_interval_s
        self._clock = clock
        self._sleep = sleep
        self._last_hit: dict[str, float] = {}

    def acquire(self, domain: str, min_interval_s: float | None = None) -> None:
        interval = self._min_interval if min_interval_s is None else min_interval_s
        last = self._last_hit.get(domain)
        now = self._clock()
        if last is not None:
            wait = interval - (now - last)
            if wait > 0:
                self._sleep(wait)
                now += wait
        self._last_hit[domain] = now
