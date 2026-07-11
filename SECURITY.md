# Security Policy

## Reporting a Vulnerability

Please report vulnerabilities privately via **GitHub Security Advisories**
("Report a vulnerability" on the Security tab) — not via public issues.
You will get an initial response within 72 hours.

## Scope & hardening rules for this codebase

- **Secrets** (LLM keys, proxy credentials, DB passwords) live only in `.env`
  (local) or a secret manager (prod). `.env` is gitignored; gitleaks runs in
  pre-commit and CI. Never log or commit credentials.
- **Fetch workers execute untrusted site content** — in production they run
  network-isolated from internal services (docs/07 §6).
- **The RAG layer never executes raw SQL from an LLM** — only parameterized,
  allow-listed functions (docs/05 §3).
- **Crawling compliance**: robots.txt, per-domain rate limits and the legal
  source registry (`sources` table) are mandatory (docs/01 §5). Do not add
  code that bypasses anti-bot protection beyond polite fingerprint parity.
- Dependencies are monitored by Dependabot; security updates are auto-raised
  as PRs into `develop`.

## Supported Versions

Only the latest release on `main` receives security fixes.
