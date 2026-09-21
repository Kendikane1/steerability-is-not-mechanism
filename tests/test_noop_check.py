"""Weight-free checks that the audit detects corruption and stops before further calls."""

from pathlib import Path
from unittest.mock import patch

import pytest
import torch
import yaml
from pydantic import ValidationError
from test_adapter_core import adapter as adapter
from test_adapter_core import strict_determinism as strict_determinism
from test_adapter_core import synthetic_model

from steerability_is_not_mechanism.adapter_core import ForwardObservation, SinglePromptAdapterCore
from steerability_is_not_mechanism.engineering_config import load_engineering_config
from steerability_is_not_mechanism.local_qwen import (
    NoOpRequest,
    load_noop_adapter,
    read_noop_request,
    read_run_request,
)
from steerability_is_not_mechanism.noop_check import PASS_NAMES, compare_values, run_noop_check

PROTOCOL = Path("configs/local_model_engineering.yaml")
REQUEST = Path("configs/local_noop.yaml")


def test_six_pass_audit_with_analytic_fixture(adapter: SinglePromptAdapterCore):
    ids = adapter.encode_decision_prompt("xy")
    starts, saved = [], []
    results = run_noop_check(
        adapter,
        ids,
        load_engineering_config(PROTOCOL).checks,
        starts.append,
        lambda name, observation, report: saved.append((name, observation, report)),
    )
    assert starts == list(PASS_NAMES)
    assert synthetic_model(adapter).calls == 6
    assert all(r["passed"] and r["exact_equal"] and r["margin_abs_error"] == 0 for r in results)
    assert saved[3][1].activation is not None and saved[4][1].activation is not None
    assert results[4]["activation_comparison"]["exact_equal"]
    assert not adapter.block._forward_hooks


def test_nonoption_logit_corruption_stops_and_retains_failure(adapter: SinglePromptAdapterCore):
    ids = adapter.encode_decision_prompt("xy")
    original = adapter.observe
    starts, reports = [], []

    def corrupt(*args, **kwargs):
        result = original(*args, **kwargs)
        logits = result.logits.clone()
        if synthetic_model(adapter).calls == 2:
            logits[10] += 0.01  # A/B margin unchanged; full-vocabulary check must detect this.
        return ForwardObservation(logits, result.activation)

    with patch.object(adapter, "observe", side_effect=corrupt):
        with pytest.raises(ValueError, match="baseline_2"):
            run_noop_check(
                adapter,
                ids,
                load_engineering_config(PROTOCOL).checks,
                starts.append,
                lambda _n, _o, r: reports.append(r),
            )
    assert synthetic_model(adapter).calls == 2
    assert not reports[-1]["passed"]
    assert reports[-1]["margin_abs_error"] < 1e-12


def test_compare_uses_reference_relative_bound_and_rejects_nonfinite():
    checks = load_engineering_config(PROTOCOL).checks
    ref = torch.tensor([0.0, 100.0])
    assert compare_values(torch.tensor([0.000009, 100.0009]), ref, checks)["elements_pass"]
    assert not compare_values(torch.tensor([0.00002, 100.0]), ref, checks)["elements_pass"]
    with pytest.raises(ValueError, match="nonfinite"):
        compare_values(torch.tensor([float("nan"), 100.0]), ref, checks)
    with pytest.raises(ValueError, match="shape"):
        compare_values(torch.ones(1), ref, checks)


@pytest.mark.parametrize(
    "field,value", [("scope", "pilot"), ("max_forward_calls", 7), ("prompt", "new")]
)
def test_noop_request_cannot_expand_scope(field, value):
    raw = yaml.safe_load(REQUEST.read_text())
    raw[field] = value
    with pytest.raises(ValidationError):
        NoOpRequest.model_validate(raw)


def test_requests_do_not_cross_execution_paths(tmp_path, monkeypatch):
    with pytest.raises(ValidationError):
        read_run_request(REQUEST, PROTOCOL)
    with pytest.raises(ValidationError):
        read_noop_request(Path("configs/local_single_item.yaml"), PROTOCOL)
    raw = yaml.safe_load(REQUEST.read_text())
    raw["execution_enabled"] = False
    disabled = tmp_path / "disabled.yaml"
    disabled.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="disabled"):
        read_noop_request(disabled, tmp_path / "missing")
    request, spec = read_noop_request(REQUEST, PROTOCOL)
    monkeypatch.setenv("HF_DEACTIVATE_ASYNC_LOAD", "1")
    with patch("steerability_is_not_mechanism.local_qwen.prepare_qwen_tokenizer") as prepare:
        with pytest.raises(ValueError, match="disabled"):
            load_noop_adapter(
                request.model_copy(update={"execution_enabled": False}),
                spec,
                tmp_path,
                tmp_path,
                torch.device("cpu"),
            )
        prepare.assert_not_called()
