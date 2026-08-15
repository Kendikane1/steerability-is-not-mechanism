"""Coordinate-only natural-dose activation interventions."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

FloatVector = NDArray[np.float64]


def _unit(direction: NDArray[np.floating]) -> FloatVector:
    vector = np.asarray(direction, dtype=np.float64)
    if vector.ndim != 1:
        raise ValueError("direction must be one-dimensional")
    norm = float(np.linalg.norm(vector))
    if not np.isclose(norm, 1.0, rtol=1e-7, atol=1e-9):
        raise ValueError("direction must be unit normalized")
    return vector


def replace_coordinate(
    activation: NDArray[np.floating],
    direction: NDArray[np.floating],
    target_coordinate: float,
) -> FloatVector:
    """Set v^T h to target_coordinate while retaining h orthogonal to v."""
    vector = _unit(direction)
    hidden = np.asarray(activation, dtype=np.float64)
    if hidden.shape != vector.shape:
        raise ValueError("activation and direction must have the same shape")
    current = float(vector @ hidden)
    return hidden + (target_coordinate - current) * vector


def paired_natural_replacements(
    pressured: NDArray[np.floating],
    low_pressure: NDArray[np.floating],
    direction: NDArray[np.floating],
) -> tuple[FloatVector, FloatVector]:
    """Return pressured→low rescue and low→pressured reverse replacement."""
    vector = _unit(direction)
    pressured_vector = np.asarray(pressured, dtype=np.float64)
    low_vector = np.asarray(low_pressure, dtype=np.float64)
    if pressured_vector.shape != vector.shape or low_vector.shape != vector.shape:
        raise ValueError("both activations must match the direction")
    z_pressured = float(vector @ pressured_vector)
    z_low = float(vector @ low_vector)
    return (
        replace_coordinate(pressured_vector, vector, z_low),
        replace_coordinate(low_vector, vector, z_pressured),
    )
