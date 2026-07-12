import pytest

from attrpipe.quality import (
    answer_accuracy,
    auto_map_rate,
    grounding_rate,
    route_distribution,
    tier_distribution,
)


class TestRatios:
    def test_answer_accuracy(self) -> None:
        assert answer_accuracy([(2300.0, 2300.0), ("IP67", "IP67"), (14.0, 20.0)]) == pytest.approx(
            2 / 3
        )

    def test_empty_is_zero(self) -> None:
        assert answer_accuracy([]) == 0.0
        assert auto_map_rate(0, 0) == 0.0
        assert grounding_rate(0, 0) == 0.0

    def test_auto_map_and_grounding(self) -> None:
        assert auto_map_rate(9, 10) == pytest.approx(0.9)
        assert grounding_rate(8, 10) == pytest.approx(0.8)


class TestDistributions:
    def test_tier_distribution(self) -> None:
        dist = tier_distribution([1, 1, 1, 3])
        assert dist["1"] == pytest.approx(0.75)
        assert dist["3"] == pytest.approx(0.25)

    def test_route_distribution(self) -> None:
        dist = route_distribution(["exact_lookup", "exact_lookup", "hybrid", "refused"])
        assert dist["exact_lookup"] == pytest.approx(0.5)
        assert dist["hybrid"] == pytest.approx(0.25)
        assert dist["refused"] == pytest.approx(0.25)
