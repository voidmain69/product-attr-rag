#!/usr/bin/env python
"""Run the universal extraction benchmark and print a report.

Discovers cases under ``tests/benchmark/cases/<vendor>/<category>/<slug>/`` and
scores attribute extraction accuracy/coverage per vendor, per category and
overall. Deterministic — no network, no LLM (docs/09 §2).

Usage:
    python tools/benchmark.py                 # human-readable report
    python tools/benchmark.py --json          # machine-readable JSON
    python tools/benchmark.py --failures      # + per-attribute misses
    python tools/benchmark.py --root PATH      # custom cases root
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from attrpipe.quality.benchmark import (  # noqa: E402  (needs sys.path tweak above)
    BenchmarkReport,
    CaseResult,
    GroupMetrics,
    evaluate_root,
)

DEFAULT_ROOT = ROOT / "tests" / "benchmark" / "cases"


def _bar(value: float, width: int = 20) -> str:
    filled = round(value * width)
    return "#" * filled + "-" * (width - filled)


def _fmt_tiers(tier_counts: dict[str, int]) -> str:
    if not tier_counts:
        return "-"
    return " ".join(f"T{tier}:{count}" for tier, count in sorted(tier_counts.items()))


def _row(label: str, m: GroupMetrics) -> str:
    return (
        f"  {label:<28} "
        f"cases={m.n_cases:>2}  attrs={m.n_expected:>3}  "
        f"acc={m.accuracy:6.1%}  cov={m.coverage:6.1%}  "
        f"[{_bar(m.accuracy)}]  {_fmt_tiers(m.tier_counts)}"
    )


def _print_group(title: str, groups: dict[str, GroupMetrics]) -> None:
    print(f"\n{title}")
    for name, metrics in groups.items():
        print(_row(name, metrics))


def _print_failures(results: list[CaseResult]) -> None:
    misses = [(r.case.name, o) for r in results for o in r.outcomes if o.status != "correct"]
    if not misses:
        print("\nNo misses — every expected attribute reproduced. ✓")
        return
    print(f"\nMisses ({len(misses)})")
    for name, outcome in misses:
        detail = (
            f"expected={outcome.expected!r}"
            if outcome.status == "missing"
            else f"expected={outcome.expected!r} got={outcome.got!r}"
        )
        print(f"  [{outcome.status:<7}] {name} :: {outcome.attribute_key} — {detail}")


def render(report: BenchmarkReport, show_failures: bool) -> None:
    o = report.overall
    print("=" * 78)
    print("attrpipe — extraction benchmark")
    print("=" * 78)
    print(
        f"  {o.n_cases} cases, {o.n_expected} expected attributes across "
        f"{len(report.by_vendor)} vendors / {len(report.by_category)} categories"
    )
    print(
        f"  accuracy {o.accuracy:.1%}  ({o.n_correct} correct, "
        f"{o.n_wrong} wrong, {o.n_missing} missing)   coverage {o.coverage:.1%}"
    )
    print(f"  tier mix: {_fmt_tiers(o.tier_counts)}")

    _print_group("By vendor", report.by_vendor)
    _print_group("By category", report.by_category)
    _print_group("By vendor / category", report.by_vendor_category)

    if show_failures:
        _print_failures(report.results)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="cases root directory")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a report")
    parser.add_argument("--failures", action="store_true", help="list per-attribute misses")
    args = parser.parse_args()

    report = evaluate_root(args.root)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return

    render(report, show_failures=args.failures)
    # Exit non-zero if anything regressed to 0 accuracy overall (useful in CI).
    sys.exit(0 if report.overall.n_expected and report.overall.accuracy > 0 else 1)


if __name__ == "__main__":
    main()
