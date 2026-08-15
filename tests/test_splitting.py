import pytest

from steerability_is_not_mechanism.data_schemas import (
    Split,
    assert_disjoint_ids,
    deterministic_family_split,
)


def test_family_split_is_deterministic_and_order_independent() -> None:
    families = [f"family-{index}" for index in range(10)]
    counts = {Split.DEVELOPMENT: 4, Split.LOCKED_TEST: 6}

    forward = deterministic_family_split(families, seed=1729, split_counts=counts)
    reverse = deterministic_family_split(list(reversed(families)), seed=1729, split_counts=counts)

    assert forward == reverse
    assert sum(split is Split.DEVELOPMENT for split in forward.values()) == 4
    assert sum(split is Split.LOCKED_TEST for split in forward.values()) == 6


def test_split_rejects_duplicate_families() -> None:
    with pytest.raises(ValueError, match="unique"):
        deterministic_family_split(["same", "same"], seed=0, split_counts={Split.DEVELOPMENT: 2})


def test_disjoint_split_guard_reports_overlap() -> None:
    with pytest.raises(ValueError, match="overlaps"):
        assert_disjoint_ids({"extraction": {"x"}, "locked": {"x"}})
