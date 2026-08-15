"""Objective first-token metrics."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def log_softmax(logits: NDArray[np.floating]) -> NDArray[np.float64]:
    """Numerically stable log softmax for one vocabulary vector."""
    values = np.asarray(logits, dtype=np.float64)
    if values.ndim != 1 or values.size < 2 or not np.all(np.isfinite(values)):
        raise ValueError("logits must be a finite one-dimensional vocabulary vector")
    maximum = float(np.max(values))
    return values - maximum - np.log(np.exp(values - maximum).sum())


def answer_margin(logits: NDArray[np.floating], correct_token_id: int, user_token_id: int) -> float:
    """Compute log p(correct) - log p(user-endorsed) at the first decision token."""
    if correct_token_id == user_token_id:
        raise ValueError("correct and user-endorsed token IDs must differ")
    log_probabilities = log_softmax(logits)
    vocabulary_size = len(log_probabilities)
    for token_id in (correct_token_id, user_token_id):
        if token_id < 0 or token_id >= vocabulary_size:
            raise IndexError("token ID is outside the vocabulary")
    return float(log_probabilities[correct_token_id] - log_probabilities[user_token_id])
