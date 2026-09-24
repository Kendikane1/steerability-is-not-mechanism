"""Separate rehearsal authorization, liveness and full-retention feasibility."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from steerability_is_not_mechanism.local_qwen import CudaEngineeringRequest, CudaRehearsalRequest
from steerability_is_not_mechanism.remote_rehearsal import check_liveness, feasibility, read_request


def test_rehearsal_scope_and_old_budget_stay_separate(tmp_path):
    raw = yaml.safe_load(Path("configs/remote_rehearsal.yaml").read_text())
    req, _ = read_request(
        Path("configs/remote_rehearsal.yaml"), Path("configs/local_model_engineering.yaml")
    )
    assert req.cycles == 12 and req.max_forward_calls == 96
    with pytest.raises(ValidationError):
        CudaEngineeringRequest.model_validate(raw)
    for key, value in [
        ("cycles", 13),
        ("max_forward_calls", 97),
        ("device", "cpu"),
        ("scope", "pilot"),
    ]:
        with pytest.raises(ValidationError):
            CudaRehearsalRequest.model_validate(raw | {key: value})
    p = tmp_path / "disabled.yaml"
    p.write_text(yaml.safe_dump(raw | {"execution_enabled": False}))
    with pytest.raises(ValueError, match="disabled"):
        read_request(p, tmp_path / "missing")


def test_feasibility_excludes_warmup_and_can_refuse_fast_cuda():
    result = feasibility([0.001, 0.001] + [2.0] * 10, 4_000_000)
    assert result["proposed_long_cycles"] == 4500
    assert not result["long_storage_feasible"]
    assert feasibility([100.0] * 12, 4_000_000)["long_storage_feasible"]
    for timings in [[1.0] * 11, [float("nan")] * 12, [0.0] * 12]:
        with pytest.raises(ValueError):
            feasibility(timings, 4_000_000)
    with pytest.raises(ValueError):
        feasibility([1.0] * 12, -1)


def test_liveness_rejects_stalled_or_unobserved_worker():
    check_liveness(None, None, 29, 0)
    with pytest.raises(TimeoutError):
        check_liveness(None, None, 31, 0)
    state = {"status": "computing", "last_progress": 90}
    check_liveness(state, {"time": 99, "finished": 99.1}, 100, 0)
    for latest in [None, {"time": 94, "finished": 94.1}, {"time": 99, "finished": 105}]:
        with pytest.raises(RuntimeError):
            check_liveness(state, latest, 100, 0)
    with pytest.raises(TimeoutError):
        check_liveness(state, {"time": 299, "finished": 299.1}, 300, 0)
