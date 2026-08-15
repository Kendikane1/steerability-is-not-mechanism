"""Independent contrastive direction estimation."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

FloatVector = NDArray[np.float64]


def estimate_mean_difference(
    loving: NDArray[np.floating], neutral: NDArray[np.floating]
) -> FloatVector:
    """Return the unit mean(loving - neutral) direction."""
    if loving.shape != neutral.shape or loving.ndim != 2:
        raise ValueError("loving and neutral activations must be matched 2D arrays")
    raw = np.asarray(loving - neutral, dtype=np.float64).mean(axis=0)
    norm = float(np.linalg.norm(raw))
    if not np.isfinite(norm) or norm == 0.0:
        raise ValueError("direction is zero or non-finite")
    return raw / norm


def pairwise_direction_accuracy(
    direction: NDArray[np.floating],
    loving: NDArray[np.floating],
    neutral: NDArray[np.floating],
) -> float:
    """Fraction of held-out pairs with loving projection above neutral."""
    if loving.shape != neutral.shape or loving.ndim != 2:
        raise ValueError("validation activations must be matched 2D arrays")
    vector = np.asarray(direction, dtype=np.float64)
    if vector.shape != (loving.shape[1],):
        raise ValueError("direction width must match activation width")
    return float(np.mean((loving - neutral) @ vector > 0.0))
