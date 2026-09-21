"""Analytic CPU fixtures only. No pretrained model, real tokenizer or scientific evidence."""

import hashlib
from collections.abc import Callable, Iterator
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from torch import nn

from steerability_is_not_mechanism.activations import ActivationSite
from steerability_is_not_mechanism.adapter_core import AdapterLayout, SinglePromptAdapterCore
from steerability_is_not_mechanism.interventions import paired_natural_replacements


class SyntheticTokenizer:
    chat_template = "SYNTHETIC character tokenizer; not Qwen"
    fault = ""

    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]:
        assert not add_special_tokens
        ids = [ord(char) for char in text]
        if self.fault == "prefix" and text.endswith("~A"):
            ids[-2] = 1
        return ids

    def decode(self, ids: list[int], *, skip_special_tokens: bool) -> str:
        assert not skip_special_tokens
        text = "".join(chr(i) for i in ids)
        return text + "!" if self.fault == "roundtrip" else text

    def apply_chat_template(
        self,
        messages: list[dict[str, str]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
        enable_thinking: bool,
        return_dict: bool,
    ) -> str | list[int]:
        assert len(messages) == 1 and messages[0]["role"] == "user"
        assert add_generation_prompt and not enable_thinking and not return_dict
        rendered = "|" + messages[0]["content"] + "~"
        if tokenize:
            ids = self.encode(rendered, add_special_tokens=False)
            return ids + [1] if self.fault == "template" else ids
        return rendered


class SyntheticBlock(nn.Module):
    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        self.original = hidden + 1
        return self.original


class SyntheticModel(nn.Module):
    scale: torch.Tensor
    after_block: torch.Tensor

    def __init__(self) -> None:
        super().__init__()
        self.block = SyntheticBlock()
        self.register_buffer("scale", torch.tensor([1.0, 2.0, 3.0, 4.0]))
        self.mode = "normal"
        self.callback: Callable[[], object] | None = None
        self.calls = 0

    def forward(self, input_ids: torch.Tensor, *, use_cache: bool) -> SimpleNamespace:
        assert not use_cache and torch.is_inference_mode_enabled() and not self.training
        self.calls += 1
        if self.callback is not None:
            self.callback()
        if self.mode == "fail_before":
            raise RuntimeError("synthetic failure before block")
        hidden = input_ids.cumsum(dim=1).float().unsqueeze(-1) * self.scale / 8
        if self.mode != "missing":
            hidden = self.block(hidden)
        if self.mode == "repeat":
            hidden = self.block(hidden)
        self.after_block = hidden.detach().clone()
        if self.mode == "fail_after":
            raise RuntimeError("synthetic failure after block")
        logits = torch.zeros(1, input_ids.shape[1], 128)
        logits[:, :, :4] = hidden * 2
        logits[:, :, 65] = hidden[:, :, 0] - hidden[:, :, 1]
        logits[:, :, 66] = hidden[:, :, 2] - hidden[:, :, 3]
        if self.mode == "nan_logits":
            logits[0, -1, 0] = float("nan")
        return SimpleNamespace(logits=logits)


@pytest.fixture(autouse=True)
def strict_determinism() -> Iterator[None]:
    previous = torch.are_deterministic_algorithms_enabled()
    warn_only = torch.is_deterministic_algorithms_warn_only_enabled()
    torch.use_deterministic_algorithms(True, warn_only=False)
    yield
    torch.use_deterministic_algorithms(previous, warn_only=warn_only)


def synthetic_model(adapter: SinglePromptAdapterCore) -> SyntheticModel:
    assert isinstance(adapter.model, SyntheticModel)
    return adapter.model


@pytest.fixture
def adapter() -> SinglePromptAdapterCore:
    tokenizer = SyntheticTokenizer()
    model = SyntheticModel().eval()
    layout = AdapterLayout(
        site=ActivationSite(1),
        hidden_size=4,
        vocabulary_size=128,
        pad_token_id=0,
        option_ids=(65, 66),
        template_sha256=hashlib.sha256(tokenizer.chat_template.encode()).hexdigest(),
        revision="SYNTHETIC-P1-009-NOT-QWEN",
    )
    return SinglePromptAdapterCore(model, model.block, tokenizer, layout, torch.device("cpu"))


def test_analytic_capture_identity_and_final_position_edit(
    adapter: SinglePromptAdapterCore,
) -> None:
    ids = adapter.encode_decision_prompt("xy")
    before = {name: value.clone() for name, value in synthetic_model(adapter).state_dict().items()}
    baseline = adapter.first_token_logits(ids)
    # Prefix sums are the fixture's explicit causal computation, not learned attention.
    expected_h = torch.tensor([1.0, 2.0, 3.0, 4.0]) * (124 + 120 + 121 + 126) / 8 + 1
    for _ in range(3):
        observation = adapter.observe(ids, adapter.layout.site)
        assert observation.activation is not None
        assert torch.equal(observation.activation, expected_h)
        assert torch.equal(observation.logits, baseline)
    identity = adapter.first_token_logits_with_replacement(ids, adapter.layout.site, expected_h)
    assert torch.equal(identity, baseline)
    replacement = expected_h.clone()
    replacement[0] += 3
    changed = adapter.first_token_logits_with_replacement(ids, adapter.layout.site, replacement)
    expected_logits = baseline.clone()
    expected_logits[0] += 6  # downstream multiplication by 2
    expected_logits[65] += 3  # independent synthetic A readout
    assert torch.equal(changed, expected_logits)
    assert torch.equal(
        synthetic_model(adapter).after_block[0, :-1],
        synthetic_model(adapter).block.original[0, :-1],
    )
    assert torch.equal(synthetic_model(adapter).block.original[0, -1], expected_h)
    assert not adapter.block._forward_hooks
    for name, value in synthetic_model(adapter).state_dict().items():
        assert torch.equal(value, before[name])
    assert torch.equal(adapter.first_token_logits(ids), baseline)


@pytest.mark.parametrize(
    "direction", [np.array([1.0, 0.0, 0.0, 0.0]), np.array([1.0, -2.0, 3.0, -4.0])]
)
def test_coordinate_and_reverse_edits_against_reference(
    adapter: SinglePromptAdapterCore,
    direction: np.ndarray,
) -> None:
    ids = adapter.encode_decision_prompt("x")
    h = adapter.capture(ids, adapter.layout.site).double().numpy()
    donor_ids = adapter.encode_decision_prompt("y")
    donor = adapter.capture(donor_ids, adapter.layout.site).double().numpy()
    v = direction / np.linalg.norm(direction)
    edited, reverse = paired_natural_replacements(h, donor, v)
    for inputs, original, target, replacement in [
        (ids, h, v @ donor, edited),
        (donor_ids, donor, v @ h, reverse),
    ]:
        actual = torch.tensor(replacement, dtype=torch.float32)
        adapter.first_token_logits_with_replacement(inputs, adapter.layout.site, actual)
        observed = synthetic_model(adapter).after_block[0, -1].double().numpy()
        scale = max(1.0, np.linalg.norm(original), np.linalg.norm(observed), abs(target))
        assert abs(v @ observed - target) <= 1e-5 * scale
        delta_orthogonal = (observed - (v @ observed) * v) - (original - (v @ original) * v)
        assert np.linalg.norm(delta_orthogonal) <= 1e-5 * scale
    identity, _ = paired_natural_replacements(h, h, v)
    baseline = adapter.first_token_logits(ids)
    zero_dose = adapter.first_token_logits_with_replacement(
        ids, adapter.layout.site, torch.tensor(identity, dtype=torch.float32)
    )
    assert torch.equal(baseline, zero_dose)
    logp = baseline.double().log_softmax(-1)
    assert float(logp[65] - logp[66]) == pytest.approx(
        float(baseline[65] - baseline[66]), abs=1e-12
    )


@pytest.mark.parametrize("mode", ["missing", "repeat", "fail_before", "fail_after", "nan_logits"])
def test_failure_removes_only_our_hook_and_adapter_can_recover(
    adapter: SinglePromptAdapterCore,
    mode: str,
) -> None:
    ids = adapter.encode_decision_prompt("x")
    prior_hook = adapter.block.register_forward_hook(lambda *_: None)
    synthetic_model(adapter).mode = mode
    try:
        with pytest.raises((RuntimeError, ValueError)):
            adapter.observe(ids, adapter.layout.site)
        assert list(adapter.block._forward_hooks) == [prior_hook.id]
        synthetic_model(adapter).mode = "normal"
        assert adapter.capture(ids, adapter.layout.site).shape == (4,)
    finally:
        prior_hook.remove()


@pytest.mark.parametrize("fault", ["prefix", "roundtrip", "template"])
def test_tokenization_faults_rejected_before_forward(adapter: SinglePromptAdapterCore, fault: str):
    assert isinstance(adapter.tokenizer, SyntheticTokenizer)
    adapter.tokenizer.fault = fault
    with pytest.raises(ValueError):
        adapter.encode_decision_prompt("x")
    assert synthetic_model(adapter).calls == 0


@pytest.mark.parametrize(
    "invalid",
    [
        torch.empty(1, 0, dtype=torch.int64),
        torch.ones(2, 2, dtype=torch.int64),
        torch.ones(1, 2),
        torch.tensor([[0]]),
        torch.tensor([[128]]),
        torch.tensor([[-1]]),
        torch.tensor([[12]]),
        torch.empty(1, 2, dtype=torch.int64, device="meta"),
    ],
)
def test_invalid_or_unissued_ids_never_reach_model(
    adapter: SinglePromptAdapterCore, invalid: torch.Tensor
):
    with pytest.raises(ValueError):
        adapter.first_token_logits(invalid)
    assert synthetic_model(adapter).calls == 0
    assert not adapter.block._forward_hooks


@pytest.mark.parametrize(
    "replacement",
    [
        torch.ones(3),
        torch.ones(4, dtype=torch.float64),
        torch.tensor([float("nan"), 1.0, 2.0, 3.0]),
    ],
)
def test_bad_replacement_rejected_before_forward(
    adapter: SinglePromptAdapterCore, replacement: torch.Tensor
):
    ids = adapter.encode_decision_prompt("x")
    with pytest.raises(ValueError):
        adapter.first_token_logits_with_replacement(ids, adapter.layout.site, replacement)
    assert synthetic_model(adapter).calls == 0
    assert not adapter.block._forward_hooks


def test_site_mutated_input_and_reentry_rejected(adapter: SinglePromptAdapterCore) -> None:
    ids = adapter.encode_decision_prompt("x")
    with pytest.raises(ValueError, match="site"):
        adapter.capture(ids, ActivationSite(0))
    mutated = ids.clone()
    mutated[0, 1] = 121
    with pytest.raises(ValueError, match="validated"):
        adapter.first_token_logits(mutated)
    synthetic_model(adapter).callback = lambda: adapter.first_token_logits(ids)
    with pytest.raises(RuntimeError, match="re-entrant"):
        adapter.capture(ids, adapter.layout.site)
    assert not adapter.block._forward_hooks
    synthetic_model(adapter).callback = None
    assert adapter.capture(ids, adapter.layout.site).shape == (4,)


def test_constructor_rejects_template_and_model_state_mismatch(adapter: SinglePromptAdapterCore):
    with pytest.raises(ValueError, match="hash"):
        SinglePromptAdapterCore(
            adapter.model,
            adapter.block,
            adapter.tokenizer,
            replace(adapter.layout, template_sha256="0" * 64),
            adapter.device,
        )
    synthetic_model(adapter).train()
    with pytest.raises(ValueError, match="evaluation"):
        adapter.first_token_logits(adapter.encode_decision_prompt("x"))
    synthetic_model(adapter).eval().double()
    with pytest.raises(ValueError, match="float32"):
        adapter.first_token_logits(adapter.encode_decision_prompt("x"))


def test_bad_block_output_is_rejected_and_hook_cleaned(adapter: SinglePromptAdapterCore):
    ids = adapter.encode_decision_prompt("x")
    corrupt = adapter.block.register_forward_hook(lambda _m, _a, output: output[:, :, :3])
    try:
        with pytest.raises(ValueError, match="block output shape"):
            adapter.capture(ids, adapter.layout.site)
        assert list(adapter.block._forward_hooks) == [corrupt.id]
    finally:
        corrupt.remove()


def test_runtime_changes_are_rejected_before_forward(adapter: SinglePromptAdapterCore):
    ids = adapter.encode_decision_prompt("x")
    with torch.autocast("cpu", dtype=torch.bfloat16):
        with pytest.raises(ValueError, match="mixed precision"):
            adapter.first_token_logits(ids)
    torch.use_deterministic_algorithms(True, warn_only=True)
    with pytest.raises(ValueError, match="strict deterministic"):
        adapter.first_token_logits(ids)
    torch.use_deterministic_algorithms(True, warn_only=False)
    assert isinstance(adapter.tokenizer, SyntheticTokenizer)
    adapter.tokenizer.chat_template = "changed"
    with pytest.raises(ValueError, match="hash mismatch"):
        adapter.first_token_logits(ids)
    assert synthetic_model(adapter).calls == 0


def test_returned_capture_has_no_alias_to_backend(adapter: SinglePromptAdapterCore):
    ids = adapter.encode_decision_prompt("x")
    captured = adapter.capture(ids, adapter.layout.site)
    reference = captured.clone()
    # Even mutating the returned capture cannot alter the model's stored block output.
    with torch.inference_mode():
        captured[0] = -100
    assert torch.equal(synthetic_model(adapter).block.original[0, -1], reference)
    assert torch.equal(adapter.capture(ids, adapter.layout.site), reference)
