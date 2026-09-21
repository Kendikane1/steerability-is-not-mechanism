"""Bounded synthetic repeatability/capture/identity audit; no changed-coordinate edits."""

from collections.abc import Callable

import torch

from .adapter_core import ForwardObservation, SinglePromptAdapterCore
from .engineering_config import EngineeringChecks

PASS_NAMES = ("baseline_1", "baseline_2", "baseline_3", "capture", "identity", "post_hook")


def compare_values(
    actual: torch.Tensor, reference: torch.Tensor, checks: EngineeringChecks
) -> dict:
    """Compare saved float32 outputs using CPU float64 arithmetic and frozen limits."""
    if actual.shape != reference.shape or actual.numel() == 0:
        raise ValueError("comparison shape mismatch or empty tensor")
    a, b = actual.detach().cpu().double(), reference.detach().cpu().double()
    if not bool(torch.isfinite(a).all() and torch.isfinite(b).all()):
        raise ValueError("nonfinite comparison")
    error = (a - b).abs()
    limit = checks.element_atol + checks.element_rtol * b.abs()
    return {
        "exact_equal": torch.equal(a, b),
        "max_abs_error": float(error.max()),
        "max_error_over_limit": float((error / limit).max()),
        "elements_pass": bool((error <= limit).all()),
    }


def checked_margin(logits: torch.Tensor, option_ids: tuple[int, int]) -> float:
    values = logits.detach().cpu().double()
    logp = values.log_softmax(-1)
    correct, endorsed = option_ids
    margin = float(logp[correct] - logp[endorsed])
    if abs(margin - float(values[correct] - values[endorsed])) > 1e-12:
        raise ValueError("log-softmax/logit margin cross-check failed")
    return margin


def run_noop_check(
    adapter: SinglePromptAdapterCore,
    ids: torch.Tensor,
    checks: EngineeringChecks,
    on_start: Callable[[str], None],
    on_result: Callable[[str, ForwardObservation, dict], None],
) -> list[dict]:
    """At most six calls, stopping at the first failure; callbacks retain partial evidence."""
    baseline = None
    captured = None
    results = []
    for name in PASS_NAMES:
        if any(m._forward_hooks or m._forward_pre_hooks for m in adapter.model.modules()):
            raise ValueError("unexpected hook before audit pass")
        on_start(name)
        observation = adapter.observe(
            ids,
            site=adapter.layout.site if name in {"capture", "identity"} else None,
            replacement=captured.clone() if name == "identity" and captured is not None else None,
        )
        hooks_clear = not any(
            m._forward_hooks or m._forward_pre_hooks for m in adapter.model.modules()
        )
        if baseline is None:
            baseline = observation.logits.detach().cpu().clone()
        report = compare_values(observation.logits, baseline, checks)
        report["name"] = name
        report["margin"] = checked_margin(observation.logits, adapter.layout.option_ids)
        report["margin_abs_error"] = abs(
            report["margin"] - checked_margin(baseline, adapter.layout.option_ids)
        )
        report["hooks_clear"] = hooks_clear
        if name == "capture":
            if observation.activation is None:
                raise ValueError("capture missing")
            captured = observation.activation.detach().clone()
        if name == "identity":
            if captured is None or observation.activation is None:
                raise ValueError("identity capture missing")
            report["activation_comparison"] = compare_values(
                observation.activation, captured, checks
            )
        report["passed"] = (
            report["elements_pass"]
            and report["margin_abs_error"] <= checks.margin_atol
            and hooks_clear
            and report.get("activation_comparison", {}).get("elements_pass", True)
        )
        on_result(name, observation, report)
        results.append(report)
        if not report["passed"]:
            raise ValueError(f"no-op comparison failed: {name}")
    return results
