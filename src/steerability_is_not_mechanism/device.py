"""Explicit local device selection with no CUDA assumption."""

from __future__ import annotations

import torch


def local_device() -> torch.device:
    """Prefer Apple MPS when available and otherwise use CPU."""
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")
