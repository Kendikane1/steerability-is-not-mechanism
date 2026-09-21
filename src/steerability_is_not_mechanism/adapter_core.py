"""Single-prompt mechanics, exercised with synthetic dependencies only.

This module loads no files/models and does not enable the guarded Qwen factory. Its injected
dependencies are trusted by the caller; their provenance must be verified by a future factory.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock
from typing import Protocol

import torch
from torch import nn

from .activations import ActivationSite


class DecisionTokenizer(Protocol):
    @property
    def chat_template(self) -> str: ...

    def apply_chat_template(
        self,
        messages: list[dict[str, str]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
        enable_thinking: bool,
        return_dict: bool,
    ) -> str | list[int]: ...

    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]: ...

    def decode(self, ids: list[int], *, skip_special_tokens: bool) -> str: ...


@dataclass(frozen=True)
class AdapterLayout:
    """Caller-supplied dimensions, not evidence of model identity."""

    site: ActivationSite
    hidden_size: int
    vocabulary_size: int
    pad_token_id: int | None
    option_ids: tuple[int, int]
    template_sha256: str
    revision: str

    def __post_init__(self) -> None:
        if self.hidden_size < 1 or self.vocabulary_size < 2:
            raise ValueError("invalid adapter dimensions")
        if len(set(self.option_ids)) != 2 or any(
            type(i) is not int or not 0 <= i < self.vocabulary_size for i in self.option_ids
        ):
            raise ValueError("option IDs must be distinct vocabulary entries")


@dataclass(frozen=True)
class ForwardObservation:
    logits: torch.Tensor
    activation: torch.Tensor | None


class SinglePromptAdapterCore:
    """Injected model must return an object with float32 logits shaped [1, T, V].

    Caller owns model setup and artifact validation. This class never moves/casts a model or
    alters process-wide runtime settings. One adapter/model owner at a time is required.
    """

    def __init__(
        self,
        model: nn.Module,
        block: nn.Module,
        tokenizer: DecisionTokenizer,
        layout: AdapterLayout,
        device: torch.device,
    ) -> None:
        if device.type not in {"cpu", "mps"}:
            raise ValueError("only local CPU/MPS devices are supported")
        if not any(module is block for module in model.modules()):
            raise ValueError("capture block must belong to the supplied model")
        self.model, self.block, self.tokenizer = model, block, tokenizer
        self.layout, self.device = layout, device
        self._lock = Lock()
        self._validated_inputs: set[str] = set()
        self._check_runtime()
        self._check_template()

    @property
    def revision(self) -> str:
        return self.layout.revision

    @contextmanager
    def _exclusive(self) -> Iterator[None]:
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("concurrent or re-entrant adapter call")
        try:
            yield
        finally:
            self._lock.release()

    def _check_runtime(self) -> None:
        if torch.is_autocast_enabled(self.device.type):
            raise ValueError("automatic mixed precision is not allowed")
        if any(module.training for module in self.model.modules()):
            raise ValueError("model and submodules must be in evaluation mode")
        if not torch.are_deterministic_algorithms_enabled() or (
            torch.is_deterministic_algorithms_warn_only_enabled()
        ):
            raise ValueError("strict deterministic algorithms must be enabled by the caller")
        for value in (*self.model.parameters(), *self.model.buffers()):
            if value.device != self.device:
                raise ValueError("model device differs from adapter device")
            if value.is_floating_point() and value.dtype != torch.float32:
                raise ValueError("model floating-point state must be float32")

    def _check_template(self) -> None:
        actual = hashlib.sha256(self.tokenizer.chat_template.encode()).hexdigest()
        if actual != self.layout.template_sha256:
            raise ValueError("tokenizer template hash mismatch")

    def _validate_ids(self, ids: torch.Tensor) -> None:
        if ids.device != self.device or ids.dtype != torch.int64:
            raise ValueError("input IDs must be int64 on the adapter device")
        if ids.ndim != 2 or ids.shape[0] != 1 or ids.shape[1] == 0:
            raise ValueError("expected one nonempty unpadded prompt [1, T]")
        if bool(((ids < 0) | (ids >= self.layout.vocabulary_size)).any()):
            raise ValueError("input token outside vocabulary")
        if self.layout.pad_token_id is not None and bool((ids == self.layout.pad_token_id).any()):
            raise ValueError("padding tokens are not accepted")

    @staticmethod
    def _fingerprint(ids: torch.Tensor) -> str:
        return hashlib.sha256(ids.detach().cpu().numpy().tobytes()).hexdigest()

    def encode_decision_prompt(self, prompt: str) -> torch.Tensor:
        with self._exclusive():
            if not prompt.strip():
                raise ValueError("prompt must be nonempty")
            self._check_template()
            messages = [{"role": "user", "content": prompt}]
            rendered = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
                return_dict=False,
            )
            ids = self.tokenizer.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                enable_thinking=False,
                return_dict=False,
            )
            if (
                not isinstance(rendered, str)
                or not isinstance(ids, list)
                or any(type(i) is not int for i in ids)
            ):
                raise ValueError("unexpected tokenizer return format")
            if ids != self.tokenizer.encode(rendered, add_special_tokens=False):
                raise ValueError("template and explicit tokenization disagree")
            if self.tokenizer.decode(ids, skip_special_tokens=False) != rendered:
                raise ValueError("prompt tokenization does not round trip")
            for label, option_id in zip(("A", "B"), self.layout.option_ids, strict=True):
                if (
                    self.tokenizer.encode(label, add_special_tokens=False) != [option_id]
                    or self.tokenizer.decode([option_id], skip_special_tokens=False) != label
                    or self.tokenizer.encode(rendered + label, add_special_tokens=False)
                    != ids + [option_id]
                ):
                    raise ValueError("ambiguous answer token or changed prompt prefix")
            tensor = torch.tensor([ids], dtype=torch.int64, device=self.device)
            self._validate_ids(tensor)
            self._validated_inputs.add(self._fingerprint(tensor))
            return tensor

    def _validate_float(self, value: object, shape: tuple[int, ...], label: str) -> torch.Tensor:
        if not isinstance(value, torch.Tensor) or tuple(value.shape) != shape:
            raise ValueError(f"invalid {label} shape")
        if value.device != self.device or value.dtype != torch.float32:
            raise ValueError(f"invalid {label} dtype/device")
        if not bool(torch.isfinite(value).all()):
            raise ValueError(f"nonfinite {label}")
        return value

    def observe(
        self,
        input_ids: torch.Tensor,
        site: ActivationSite | None = None,
        replacement: torch.Tensor | None = None,
    ) -> ForwardObservation:
        """One forward; optionally capture pre-edit activation and replace that same site."""
        with self._exclusive(), torch.inference_mode():
            self._check_runtime()
            self._check_template()
            self._validate_ids(input_ids)
            if self._fingerprint(input_ids) not in self._validated_inputs:
                raise ValueError("input IDs were not validated by this adapter")
            if site is not None and site != self.layout.site:
                raise ValueError("activation site differs from adapter layout")
            if replacement is not None:
                if site is None:
                    raise ValueError("replacement requires a capture site")
                replacement = (
                    self._validate_float(replacement, (self.layout.hidden_size,), "replacement")
                    .detach()
                    .clone()
                )
            sequence_length = input_ids.shape[1]
            count = 0
            captured: torch.Tensor | None = None

            def hook(_module: nn.Module, _args: tuple[object, ...], output: object):
                nonlocal count, captured
                count += 1
                if count != 1:
                    raise RuntimeError("capture block invoked more than once")
                tensor = self._validate_float(
                    output, (1, sequence_length, self.layout.hidden_size), "block output"
                )
                captured = tensor[0, -1, :].detach().clone()
                if replacement is None:
                    return None
                edited = tensor.clone()
                edited[0, -1, :] = replacement
                return edited

            handle = self.block.register_forward_hook(hook) if site is not None else None
            try:
                result = self.model(input_ids=input_ids.clone(), use_cache=False)
                if site is not None and count != 1:
                    raise RuntimeError("capture block was not invoked")
                logits = self._validate_float(
                    getattr(result, "logits", None),
                    (1, sequence_length, self.layout.vocabulary_size),
                    "logits",
                )
                return ForwardObservation(logits[0, -1, :].detach().clone(), captured)
            finally:
                if handle is not None:
                    handle.remove()

    def first_token_logits(self, input_ids: torch.Tensor) -> torch.Tensor:
        return self.observe(input_ids).logits

    def capture(self, input_ids: torch.Tensor, site: ActivationSite) -> torch.Tensor:
        result = self.observe(input_ids, site)
        assert result.activation is not None
        return result.activation

    def first_token_logits_with_replacement(
        self,
        input_ids: torch.Tensor,
        site: ActivationSite,
        replacement: torch.Tensor,
    ) -> torch.Tensor:
        return self.observe(input_ids, site, replacement).logits
