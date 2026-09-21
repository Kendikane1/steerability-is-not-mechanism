"""Analytic fixtures and deliberately broken edits; never pretrained/scientific evidence."""

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import yaml
from pydantic import ValidationError
from test_adapter_core import adapter as adapter
from test_adapter_core import strict_determinism as strict_determinism
from test_adapter_core import synthetic_model

from steerability_is_not_mechanism.adapter_core import SinglePromptAdapterCore
from steerability_is_not_mechanism.coordinate_check import (
    geometry_report,
    run_coordinate_check,
    synthetic_directions,
)
from steerability_is_not_mechanism.engineering_config import load_engineering_config
from steerability_is_not_mechanism.interventions import paired_natural_replacements
from steerability_is_not_mechanism.local_qwen import (
    CoordinateRequest,
    read_coordinate_request,
    read_noop_request,
    read_run_request,
)

PROTOCOL = Path("configs/local_model_engineering.yaml")
REQUEST = Path("configs/local_coordinate.yaml")


def test_full_paired_audit_and_actual_hook_output(adapter: SinglePromptAdapterCore):
    inputs = {
        "high": adapter.encode_decision_prompt("x"),
        "low": adapter.encode_decision_prompt("y"),
    }
    starts, outputs = [], []
    results = run_coordinate_check(
        adapter,
        inputs,
        load_engineering_config(PROTOCOL).checks,
        starts.append,
        lambda n, o, r: outputs.append((n, o, r)),
    )
    assert len(starts) == synthetic_model(adapter).calls == 18
    assert all(r["passed"] for r in results)
    edits = [(o, r) for _, o, r in outputs if o.applied_replacement is not None]
    assert len(edits) == 8
    assert all(r["geometry"]["passed"] and r["unedited_positions_exact"] for _, r in edits)
    assert all(r["logit_comparison"]["exact_equal"] for r in results if "_paired_" not in r["name"])
    assert any(r["margin_delta"] != 0 for r in results if "_paired_" in r["name"])
    assert not adapter.block._forward_hooks


def test_corrupt_coordinate_math_stops_before_next_forward(adapter: SinglePromptAdapterCore):
    inputs = {
        "high": adapter.encode_decision_prompt("x"),
        "low": adapter.encode_decision_prompt("y"),
    }
    saved = []

    def corrupt(*args):
        high, low = paired_natural_replacements(*args)
        high[1] += 1  # axis0 target can be correct while orthogonal preservation is wrong.
        return high, low

    with patch(
        "steerability_is_not_mechanism.coordinate_check.paired_natural_replacements",
        side_effect=corrupt,
    ):
        with pytest.raises(ValueError, match="axis0_paired_high"):
            run_coordinate_check(
                adapter,
                inputs,
                load_engineering_config(PROTOCOL).checks,
                lambda _n: None,
                lambda n, o, r: saved.append(r),
            )
    assert synthetic_model(adapter).calls == 10
    assert not saved[-1]["geometry"]["passed"]
    assert saved[-1]["geometry"]["projection_error"] == 0
    assert not adapter.block._forward_hooks


def test_geometry_rejects_projection_and_orthogonal_errors():
    checks = load_engineering_config(PROTOCOL).checks
    h, donor, v = np.array([1.0, 2.0]), np.array([3.0, 4.0]), np.array([1.0, 0.0])
    assert geometry_report(h, [3.0, 2.0], donor, v, checks)["passed"]
    assert not geometry_report(h, [1.0, 2.0], donor, v, checks)["passed"]
    assert not geometry_report(h, [3.0, 4.0], donor, v, checks)["passed"]
    with pytest.raises(ValueError, match="nonfinite"):
        geometry_report(h, [float("nan"), 2.0], donor, v, checks)
    for v in synthetic_directions(1024).values():
        assert np.linalg.norm(v) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("scope", "pilot"),
        ("max_forward_calls", 19),
        ("directions", "chosen_from_scores"),
        ("low_prompt", "other"),
    ],
)
def test_coordinate_request_cannot_expand_scope(field, value):
    raw = yaml.safe_load(REQUEST.read_text())
    raw[field] = value
    with pytest.raises(ValidationError):
        CoordinateRequest.model_validate(raw)


def test_coordinate_request_disabled_and_isolated(tmp_path):
    request, _ = read_coordinate_request(REQUEST, PROTOCOL)
    assert request.max_forward_calls == 18
    for reader in (read_run_request, read_noop_request):
        with pytest.raises(ValidationError):
            reader(REQUEST, PROTOCOL)
    raw = yaml.safe_load(REQUEST.read_text())
    raw["execution_enabled"] = False
    path = tmp_path / "disabled.yaml"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="disabled"):
        read_coordinate_request(path, tmp_path / "missing")
