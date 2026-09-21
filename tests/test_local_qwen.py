"""Offline request/loader rejection tests; never construct a pretrained model."""

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest
import torch
import yaml
from pydantic import ValidationError

from steerability_is_not_mechanism.local_qwen import (
    SingleItemRequest,
    configure_runtime,
    load_single_item_adapter,
    read_run_request,
)

REQUEST = Path("configs/local_single_item.yaml")
PROTOCOL = Path("configs/local_model_engineering.yaml")


def test_single_item_record_matches_frozen_protocol():
    request, spec = read_run_request(REQUEST, PROTOCOL)
    assert request.max_forward_calls == 1
    assert request.execution_enabled
    assert not spec.execution_enabled and not spec.model.allow_download


@pytest.mark.parametrize("requested", ["auto", "mps"])
def test_mps_selection_uses_explicit_tensor_device_ordinal(monkeypatch, requested):
    _, spec = read_run_request(REQUEST, PROTOCOL)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.setenv("PYTORCH_ENABLE_MPS_FALLBACK", "0")
    prefix = "steerability_is_not_mechanism.local_qwen."
    with ExitStack() as stack:
        stack.enter_context(patch(prefix + "local_device", return_value=torch.device("mps")))
        stack.enter_context(patch("torch.backends.mps.is_available", return_value=True))
        for name in (
            "torch.set_num_threads",
            "torch.set_num_interop_threads",
            "torch.manual_seed",
            "torch.use_deterministic_algorithms",
            "random.seed",
            "np.random.seed",
        ):
            stack.enter_context(patch(prefix + name))
        assert configure_runtime(spec, requested) == torch.device("mps:0")


def test_disabled_record_fails_before_artifact_access(tmp_path: Path):
    raw = yaml.safe_load(REQUEST.read_text())
    raw["execution_enabled"] = False
    path = tmp_path / "disabled.yaml"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="disabled"):
        read_run_request(path, tmp_path / "absent-protocol.yaml")


def test_changed_protocol_rejected(tmp_path: Path):
    changed = tmp_path / "protocol.yaml"
    changed.write_text(PROTOCOL.read_text() + "\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        read_run_request(REQUEST, changed)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("scope", "pilot"),
        ("max_forward_calls", 2),
        ("prompt", "another question"),
        ("device", "cuda"),
        ("weights_sha256", "0" * 64),
        ("correct_token_id", 33),
        ("allow_download", True),
    ],
)
def test_request_cannot_expand_scope(key: str, value: object):
    raw = yaml.safe_load(REQUEST.read_text())
    raw[key] = value
    with pytest.raises(ValidationError):
        SingleItemRequest.model_validate(raw)


def test_factory_disabled_before_tokenizer_or_weight_access(tmp_path: Path):
    request, spec = read_run_request(REQUEST, PROTOCOL)
    disabled = request.model_copy(update={"execution_enabled": False})
    with patch("steerability_is_not_mechanism.local_qwen.prepare_qwen_tokenizer") as prepare:
        with pytest.raises(ValueError, match="disabled"):
            load_single_item_adapter(disabled, spec, tmp_path, tmp_path, torch.device("cpu"))
        prepare.assert_not_called()


@pytest.mark.parametrize("problem", ["online", "implicit_fallback"])
def test_runtime_refuses_unrecorded_network_or_fallback(
    monkeypatch: pytest.MonkeyPatch, problem: str
):
    _, spec = read_run_request(REQUEST, PROTOCOL)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    if problem == "online":
        monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    else:
        monkeypatch.setenv("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    with pytest.raises(ValueError):
        configure_runtime(spec, "cpu")
