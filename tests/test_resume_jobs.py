"""Small analytic fixture jobs and literal request guards."""

from pathlib import Path

import numpy as np
import pytest
import yaml
from pydantic import ValidationError
from test_adapter_core import adapter as adapter
from test_adapter_core import strict_determinism as strict_determinism

from steerability_is_not_mechanism.adapter_core import SinglePromptAdapterCore
from steerability_is_not_mechanism.engineering_config import load_engineering_config
from steerability_is_not_mechanism.local_qwen import ResumeRequest, read_resume_request
from steerability_is_not_mechanism.resume_jobs import (
    compute_job,
    jobs_for_shard,
    synthetic_jobs,
    unpack,
)


def test_fixed_partition_and_independent_jobs(adapter: SinglePromptAdapterCore):
    rows = synthetic_jobs()
    partition = jobs_for_shard(0) + jobs_for_shard(1)
    assert sorted(r.run_id for r in partition) == [r.run_id for r in rows]
    assert len({r.run_id for r in partition}) == 4
    inputs = {
        "high": adapter.encode_decision_prompt("x"),
        "low": adapter.encode_decision_prompt("y"),
    }
    spec = load_engineering_config(Path("configs/local_model_engineering.yaml"))
    calls = []
    outputs = {}
    for row in reversed(rows):
        metadata, blob = compute_job(row, adapter, inputs, spec, lambda: calls.append(1))
        outputs[row.run_id] = unpack(blob)
        assert metadata["hooks_clear"]
        if row.intervention == "edit":
            assert metadata["geometry"]["passed"] and metadata["unedited_positions_exact"]
    assert len(calls) == 8
    for row in rows:
        _, blob = compute_job(row, adapter, inputs, spec, lambda: None)
        assert all(np.array_equal(a, outputs[row.run_id][k]) for k, a in unpack(blob).items())


@pytest.mark.parametrize(
    "field,value",
    [("scope", "pilot"), ("shard_count", 3), ("max_forward_calls", 9), ("jobs", "new")],
)
def test_resume_scope_cannot_expand(field, value):
    raw = yaml.safe_load(Path("configs/local_resume.yaml").read_text())
    raw[field] = value
    with pytest.raises(ValidationError):
        ResumeRequest.model_validate(raw)


def test_disabled_resume_rejected_before_protocol(tmp_path):
    raw = yaml.safe_load(Path("configs/local_resume.yaml").read_text())
    raw["execution_enabled"] = False
    path = tmp_path / "request.yaml"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="disabled"):
        read_resume_request(path, tmp_path / "missing")
