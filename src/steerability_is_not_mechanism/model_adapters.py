"""Model adapter boundaries without any Phase 0 weight loading."""

from __future__ import annotations

from typing import Protocol

import torch

from .activations import ActivationSite


class CausalLMAdapter(Protocol):
    """Single unpadded prompt contract; concrete model execution is still disabled.

    See docs/LOCAL_ENGINEERING_PROTOCOL.md for required runtime validation and hook cleanup.
    These method declarations do not implement those guarantees.
    """

    @property
    def revision(self) -> str: ...

    def encode_decision_prompt(self, prompt: str) -> torch.Tensor:
        """Return int64 [1, sequence_length] IDs after template/prefix/option checks."""
        ...

    def first_token_logits(self, input_ids: torch.Tensor) -> torch.Tensor:
        """Return finite float32 [vocabulary_size] logits at the final input position."""
        ...

    def capture(self, input_ids: torch.Tensor, site: ActivationSite) -> torch.Tensor:
        """Return a detached float32 [hidden_size] clone at the declared block output."""
        ...

    def first_token_logits_with_replacement(
        self, input_ids: torch.Tensor, site: ActivationSite, replacement: torch.Tensor
    ) -> torch.Tensor:
        """Accept a finite same-device/dtype [hidden_size] vector; return final logits.

        The caller constructs the coordinate replacement. The adapter validates it, clones the
        block output and replaces only the selected token. It never edits weights or leaves a
        hook registered after the call, including when the forward pass raises.
        """
        ...


class ModelLoadingDeferred(RuntimeError):
    """Raised when Phase 0 code is asked to download or load a model."""


def load_qwen_adapter() -> CausalLMAdapter:
    """Phase 1 extension point, deliberately disabled during initialization."""
    raise ModelLoadingDeferred(
        "Model loading is deferred until Phase 1 revisions and token conventions are frozen."
    )
