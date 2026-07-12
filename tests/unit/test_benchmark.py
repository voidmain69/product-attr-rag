"""Unit tests for the extraction benchmark harness (attrpipe.quality.benchmark)."""

import json
from pathlib import Path

from attrpipe.quality.benchmark import (
    BenchmarkCase,
    discover_cases,
    evaluate,
    evaluate_root,
    run_case,
)

CASES_ROOT = Path(__file__).resolve().parent.parent / "benchmark" / "cases"


class TestDiscovery:
    def test_finds_all_seeded_cases(self) -> None:
        cases = discover_cases(CASES_ROOT)
        names = {c.name for c in cases}
        assert "asus/motherboards/rog-strix-b650e-f" in names
        assert "msi/graphics_cards/rtx-4070-gaming-x-trio" in names
        assert "intel/processors/core-i7-14700k" in names
        # vendor/category are parsed from the path, not the file.
        asus = next(c for c in cases if c.slug == "rog-swift-pg27aqdm")
        assert (asus.vendor, asus.category) == ("asus", "monitors")
        assert asus.content_type == "text/html"


class TestSeededSetPasses:
    """The seeded golden set is designed to extract at 100% — a regression floor."""

    def test_overall_accuracy_is_perfect(self) -> None:
        report = evaluate_root(CASES_ROOT)
        assert report.overall.n_cases == 6
        assert report.overall.accuracy == 1.0, [
            (r.case.name, o.attribute_key, o.status, o.got, o.expected)
            for r in report.results
            for o in r.outcomes
            if o.status != "correct"
        ]
        assert report.overall.coverage == 1.0

    def test_groups_present(self) -> None:
        report = evaluate_root(CASES_ROOT)
        assert set(report.by_vendor) == {"asus", "msi", "intel"}
        assert "asus/motherboards" in report.by_vendor_category

    def test_tier_mix_uses_cheap_tiers(self) -> None:
        report = evaluate_root(CASES_ROOT)
        # ASUS motherboard is JSON-LD (Tier 1); the rest are DOM tables (Tier 3).
        assert "1" in report.overall.tier_counts
        assert "3" in report.overall.tier_counts
        assert "4" not in report.overall.tier_counts  # never the LLM in the benchmark


class TestUnitConversions:
    def test_terabyte_storage_converts_to_gb(self) -> None:
        report = evaluate_root(CASES_ROOT)
        laptop = next(r for r in report.results if r.case.slug == "rog-zephyrus-g14")
        storage = next(o for o in laptop.outcomes if o.attribute_key == "storage")
        assert storage.status == "correct"
        assert storage.got == 1024.0  # "1 TB" -> canonical GB

    def test_ghz_and_mhz_kept_distinct(self) -> None:
        report = evaluate_root(CASES_ROOT)
        cpu = next(r for r in report.results if r.case.slug == "core-i7-14700k")
        base = next(o for o in cpu.outcomes if o.attribute_key == "cpu_base_clock")
        assert base.got == 3.4  # GHz
        gpu = next(r for r in report.results if r.case.slug == "rtx-4070-gaming-x-trio")
        boost = next(o for o in gpu.outcomes if o.attribute_key == "gpu_boost_clock")
        assert boost.got == 2640.0  # MHz


class TestScoringStatuses:
    def _write_case(self, tmp_path: Path, expected: dict[str, object], html: str) -> BenchmarkCase:
        slug_dir = tmp_path / "acme" / "widgets" / "w1"
        slug_dir.mkdir(parents=True)
        (slug_dir / "source.html").write_text(html, encoding="utf-8")
        (slug_dir / "expected.json").write_text(
            json.dumps({"expected": expected}), encoding="utf-8"
        )
        return discover_cases(tmp_path)[0]

    def test_wrong_and_missing_are_flagged(self, tmp_path: Path) -> None:
        html = (
            "<table><tr><th>Socket</th><td>AM5</td></tr>"
            "<tr><th>Chipset</th><td>B650</td></tr></table>"
        )
        case = self._write_case(
            tmp_path,
            {"socket": "AM5", "chipset": "X999", "form_factor": "ATX"},
            html,
        )
        result = run_case(case)
        by_key = {o.attribute_key: o.status for o in result.outcomes}
        assert by_key == {"socket": "correct", "chipset": "wrong", "form_factor": "missing"}
        assert result.accuracy == 1 / 3

    def test_evaluate_accepts_explicit_cases(self, tmp_path: Path) -> None:
        html = "<table><tr><th>Socket</th><td>AM5</td></tr></table>"
        case = self._write_case(tmp_path, {"socket": "AM5"}, html)
        report = evaluate([case])
        assert report.overall.accuracy == 1.0
        assert report.by_vendor["acme"].n_cases == 1
