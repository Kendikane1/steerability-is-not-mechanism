"""Activation capture contracts; concrete hooks arrive in Phase 1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import torch

LiteralPosition = Literal["pre_answer_final_assistant_delimiter"]


@dataclass(frozen=True)
class ActivationSite:
    """Zero-based block output, before downstream normalization, at the input boundary.

    The legacy token-position name means the last non-padding token of the entire formatted
    input, including template suffixes; it does not mean an earlier assistant header token.
    Model-specific upper bounds are checked by the adapter against its loaded architecture.
    """

    layer_index: int
    token_position: LiteralPosition = "pre_answer_final_assistant_delimiter"
    stream: Literal["residual"] = "residual"
    boundary: Literal["block_output_after_residual_additions_before_downstream_norm"] = (
        "block_output_after_residual_additions_before_downstream_norm"
    )

    def __post_init__(self) -> None:
        if type(self.layer_index) is not int or self.layer_index < 0:
            raise ValueError("layer_index must be a nonnegative zero-based integer")
        if (
            self.token_position != "pre_answer_final_assistant_delimiter"
            or self.stream != "residual"
            or self.boundary != "block_output_after_residual_additions_before_downstream_norm"
        ):
            raise ValueError("unsupported activation boundary")


class ActivationCapture(Protocol):
    """Adapter-neutral single-position capture/replacement interface."""

    def capture(self, input_ids: torch.Tensor, site: ActivationSite) -> torch.Tensor: ...

    def next_token_logits_with_replacement(
        self, input_ids: torch.Tensor, site: ActivationSite, replacement: torch.Tensor
    ) -> torch.Tensor: ...
