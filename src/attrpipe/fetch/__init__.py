"""Fetch — static/headless fetcher pool, politeness, Raw Store (docs/01).

Rules baked into this layer:
- static-first; headless only when embedded/API data is unavailable;
- per-domain token buckets, robots.txt and Crawl-delay respected;
- every response lands in the Raw Store with full fetch provenance
  (url, fetched_at, http_status, content_hash, render_mode, detected_engine).
"""
