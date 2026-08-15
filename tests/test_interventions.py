import numpy as np
import pytest

from steerability_is_not_mechanism.interventions import (
    paired_natural_replacements,
    replace_coordinate,
)


def test_replace_coordinate_sets_target_and_preserves_orthogonal_component() -> None:
    direction = np.array([3.0, 4.0]) / 5.0
    activation = np.array([7.0, -2.0])
    target = -1.25

    replaced = replace_coordinate(activation, direction, target)
    old_orthogonal = activation - (direction @ activation) * direction
    new_orthogonal = replaced - (direction @ replaced) * direction

    assert direction @ replaced == pytest.approx(target)
    np.testing.assert_allclose(new_orthogonal, old_orthogonal, atol=1e-12)


def test_paired_replacements_swap_only_the_natural_coordinates() -> None:
    direction = np.array([1.0, 0.0, 0.0])
    pressured = np.array([4.0, 2.0, -1.0])
    low = np.array([1.0, 3.0, 5.0])

    rescued, induced = paired_natural_replacements(pressured, low, direction)

    np.testing.assert_allclose(rescued, [1.0, 2.0, -1.0])
    np.testing.assert_allclose(induced, [4.0, 3.0, 5.0])


def test_replacement_rejects_nonunit_direction() -> None:
    with pytest.raises(ValueError, match="unit normalized"):
        replace_coordinate(np.array([1.0, 2.0]), np.array([2.0, 0.0]), 0.0)
