"""CUDA scope and resource checks; these tests never load pretrained weights."""

from pathlib import Path
from unittest.mock import patch

import pytest
import torch
import yaml
from pydantic import ValidationError

from steerability_is_not_mechanism.local_qwen import (
    CudaEngineeringRequest,
    SingleItemRequest,
    load_single_item_adapter,
    read_run_request,
)
from steerability_is_not_mechanism.remote_cuda import (
    GIB,
    check_resources,
    configure_cuda,
    read_cuda_request,
)


@pytest.mark.parametrize(
    "mode,budget", [("single", 1), ("noop", 6), ("coordinate", 18), ("resume", 8)]
)
def test_exact_cuda_modes(mode, budget):
    request, spec = read_cuda_request(
        Path(f"configs/remote_{mode}.yaml"), Path("configs/local_model_engineering.yaml")
    )
    assert request.max_forward_calls == budget and not spec.execution_enabled
    with pytest.raises(ValidationError):
        CudaEngineeringRequest.model_validate(
            request.model_dump() | {"max_forward_calls": budget + 1}
        )
    with pytest.raises(ValidationError):
        SingleItemRequest.model_validate(request.model_dump())


@pytest.mark.parametrize(
    "key,value",
    [
        ("scope", "pilot"),
        ("device", "cpu"),
        ("prompt", "different"),
        ("weights_sha256", "x"),
        ("mode", "sustained"),
    ],
)
def test_cuda_scope_rejection(key, value):
    raw = yaml.safe_load(Path("configs/remote_single.yaml").read_text())
    with pytest.raises(ValidationError):
        CudaEngineeringRequest.model_validate(raw | {key: value})


def test_disabled_cuda_fails_before_artifact_read(tmp_path):
    raw = yaml.safe_load(Path("configs/remote_single.yaml").read_text())
    path = tmp_path / "request.yaml"
    path.write_text(yaml.safe_dump(raw | {"execution_enabled": False}))
    with pytest.raises(ValueError, match="disabled"):
        read_cuda_request(path, tmp_path / "missing")


def test_local_factory_still_refuses_cuda(tmp_path):
    request, spec = read_run_request(
        Path("configs/local_single_item.yaml"), Path("configs/local_model_engineering.yaml")
    )
    with patch("steerability_is_not_mechanism.local_qwen.prepare_qwen_tokenizer") as prepare:
        with pytest.raises(ValueError, match="unsupported execution device"):
            load_single_item_adapter(request, spec, tmp_path, tmp_path, torch.device("cuda:0"))
        prepare.assert_not_called()


def test_cuda_runtime_refuses_unreviewed_platform(monkeypatch):
    monkeypatch.setattr("steerability_is_not_mechanism.remote_cuda.sys.platform", "darwin")
    with pytest.raises(ValueError, match="Windows"):
        configure_cuda(None)


def test_windows_resource_limits():
    baseline = {
        "gpu_free": 5 * GIB,
        "disk_free": 21 * GIB,
        "ram": {"avail_phys": 2 * GIB, "avail_commit": 3 * GIB, "load": 50},
    }
    check_resources(baseline, True)
    for row in [
        baseline | {"gpu_free": GIB - 1},
        baseline | {"disk_free": 20 * GIB - 1},
        baseline | {"ram": baseline["ram"] | {"avail_phys": GIB // 2 - 1}},
        baseline | {"ram": baseline["ram"] | {"load": 95}},
    ]:
        with pytest.raises(RuntimeError):
            check_resources(row, False)
    with pytest.raises(RuntimeError):
        check_resources(baseline | {"gpu_free": 4 * GIB - 1}, True)


def test_worker_pid_must_be_owned_child(monkeypatch):
    from steerability_is_not_mechanism.process_control import validate_worker_pid

    validate_worker_pid(123, 123)
    monkeypatch.setattr("subprocess.check_output", lambda *a, **kw: "123\n")
    validate_worker_pid(123, 456)
    monkeypatch.setattr("subprocess.check_output", lambda *a, **kw: "999\n")
    with pytest.raises(ValueError, match="owned"):
        validate_worker_pid(123, 456)
    with pytest.raises(ValueError, match="invalid"):
        validate_worker_pid(123, -1)
