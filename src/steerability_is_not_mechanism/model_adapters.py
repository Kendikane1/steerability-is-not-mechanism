"""Model adapter boundaries without any Phase 0 weight loading."""

from __future__ import annotations

from typing import Protocol

import torch

from .activations import ActivationSite


class CausalLMAdapter(Protocol):
    """Minimal contract required by the future experiment runner."""

    @property
    def revision(self) -> str: ...

    def encode_decision_prompt(self, prompt: str) -> torch.Tensor: ...

    def first_token_logits(self, input_ids: torch.Tensor) -> torch.Tensor: ...

    def capture(self, input_ids: torch.Tensor, site: ActivationSite) -> torch.Tensor: ...

    def first_token_logits_with_replacement(
        self, input_ids: torch.Tensor, site: ActivationSite, replacement: torch.Tensor
    ) -> torch.Tensor: ...


class ModelLoadingDeferred(RuntimeError):
    """Raised when Phase 0 code is asked to download or load a model."""


def load_qwen_adapter() -> CausalLMAdapter:
    """Phase 1 extension point, deliberately disabled during initialization."""
    raise ModelLoadingDeferred(
        "Model loading is deferred until Phase 1 revisions and token conventions are frozen."
    )
