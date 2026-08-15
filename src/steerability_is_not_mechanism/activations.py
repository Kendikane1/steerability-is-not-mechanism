"""Activation capture contracts; concrete hooks arrive in Phase 1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import torch

LiteralPosition = Literal["pre_answer_final_assistant_delimiter"]


@dataclass(frozen=True)
class ActivationSite:
    layer_index: int
    token_position: LiteralPosition = "pre_answer_final_assistant_delimiter"
    stream: Literal["residual"] = "residual"


class ActivationCapture(Protocol):
    """Adapter-neutral single-position capture/replacement interface."""

    def capture(self, input_ids: torch.Tensor, site: ActivationSite) -> torch.Tensor: ...

    def next_token_logits_with_replacement(
        self, input_ids: torch.Tensor, site: ActivationSite, replacement: torch.Tensor
    ) -> torch.Tensor: ...
