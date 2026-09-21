"""Synthetic paired-coordinate engineering audit, never a scientific direction estimate."""

from collections.abc import Callable

import numpy as np
import torch

from .adapter_core import ForwardObservation, SinglePromptAdapterCore
from .engineering_config import EngineeringChecks
from .interventions import paired_natural_replacements, replace_coordinate
from .noop_check import checked_margin, compare_values


def synthetic_directions(width: int) -> dict[str, np.ndarray]:
    axis = np.zeros(width, dtype=np.float64)
    axis[0] = 1
    dense = np.where(np.arange(width) % 2 == 0, 1.0, -1.0)
    dense /= np.linalg.norm(dense)
    return {"axis0": axis, "alternating": dense}


def geometry_report(original, applied, donor, direction, checks: EngineeringChecks) -> dict:
    """Audit actual float32 hook output in CPU float64; donor is an observed activation."""
    h, edited, other, v = [
        np.asarray(x, dtype=np.float64) for x in (original, applied, donor, direction)
    ]
    if h.ndim != 1 or not all(x.shape == h.shape for x in (edited, other, v)):
        raise ValueError("geometry shape mismatch")
    if not all(np.isfinite(x).all() for x in (h, edited, other, v)):
        raise ValueError("nonfinite geometry")
    if not np.isclose(np.linalg.norm(v), 1, rtol=1e-7, atol=1e-9):
        raise ValueError("geometry direction must be unit")
    current, target, observed = float(v @ h), float(v @ other), float(v @ edited)
    orthogonal_error = float(np.linalg.norm((edited - observed * v) - (h - current * v)))
    scale = max(1.0, float(np.linalg.norm(h)), float(np.linalg.norm(edited)), abs(target))
    limit = checks.geometry_scaled_atol * scale
    projection_error = abs(observed - target)
    return {
        "original_coordinate": current,
        "target_coordinate": target,
        "applied_coordinate": observed,
        "projection_error": projection_error,
        "orthogonal_error_l2": orthogonal_error,
        "scale": scale,
        "limit": limit,
        "edit_norm_l2": float(np.linalg.norm(edited - h)),
        "passed": projection_error <= limit and orthogonal_error <= limit,
    }


def run_coordinate_check(
    adapter: SinglePromptAdapterCore,
    inputs: dict[str, torch.Tensor],
    checks: EngineeringChecks,
    on_start: Callable[[str], None],
    on_result: Callable[[str, ForwardObservation, dict], None],
) -> list[dict]:
    """18 calls maximum; save each valid observation and fail at the first bad audit."""
    if set(inputs) != {"high", "low"}:
        raise ValueError("expected exactly the synthetic high/low pair")
    baselines: dict[str, torch.Tensor] = {}
    captures: dict[str, torch.Tensor] = {}
    reports = []

    def forward(name, context, capture=False, replacement=None, donor=None, direction=None):
        if any(m._forward_hooks or m._forward_pre_hooks for m in adapter.model.modules()):
            raise ValueError("unexpected pre-existing hooks")
        on_start(name)
        obs = adapter.observe(
            inputs[context], adapter.layout.site if capture else None, replacement
        )
        clean = not any(m._forward_hooks or m._forward_pre_hooks for m in adapter.model.modules())
        if context not in baselines:
            baselines[context] = obs.logits.detach().cpu().clone()
        comparison = compare_values(obs.logits, baselines[context], checks)
        margin = checked_margin(obs.logits, adapter.layout.option_ids)
        baseline_margin = checked_margin(baselines[context], adapter.layout.option_ids)
        logp = obs.logits.detach().cpu().double().log_softmax(-1)
        a, b = adapter.layout.option_ids
        report = {
            "name": name,
            "context": context,
            "margin": margin,
            "margin_delta": margin - baseline_margin,
            "p_A": float(logp[a].exp()),
            "p_B": float(logp[b].exp()),
            "logit_comparison": comparison,
            "hooks_clear": clean,
            "passed": clean,
        }
        if capture:
            if obs.activation is None:
                raise ValueError("missing capture")
            if context not in captures:
                captures[context] = obs.activation.detach().cpu().clone()
            capture_check = compare_values(obs.activation, captures[context], checks)
            report["capture_comparison"] = capture_check
            report["passed"] &= capture_check["elements_pass"]
        if replacement is not None:
            if obs.applied_replacement is None:
                raise ValueError("missing actual applied replacement")
            report["applied_matches_requested"] = torch.equal(obs.applied_replacement, replacement)
            report["unedited_positions_exact"] = obs.unedited_positions_exact
            report["geometry"] = geometry_report(
                captures[context].numpy(),
                obs.applied_replacement.detach().cpu().numpy(),
                donor,
                direction,
                checks,
            )
            report["passed"] &= (
                report["applied_matches_requested"]
                and obs.unedited_positions_exact is True
                and report["geometry"]["passed"]
            )
        # Scores may change for paired edits. Their sign/size never defines success.
        if "_paired_" not in name:
            report["passed"] &= (
                comparison["elements_pass"] and abs(report["margin_delta"]) <= checks.margin_atol
            )
        on_result(name, obs, report)
        reports.append(report)
        if not report["passed"]:
            raise ValueError(f"coordinate audit failed: {name}")

    for context in ("high", "low"):
        for i in range(checks.baseline_repetitions):
            forward(f"{context}_baseline_{i + 1}", context)
        forward(f"{context}_capture", context, capture=True)
    high, low = (captures[c].numpy().astype(np.float64) for c in ("high", "low"))
    for label, v in synthetic_directions(adapter.layout.hidden_size).items():
        paired = paired_natural_replacements(high, low, v)
        for context, original, donor, edit in (
            ("high", high, low, paired[0]),
            ("low", low, high, paired[1]),
        ):
            zero = replace_coordinate(original, v, float(v @ original))
            for kind, value, target in (("zero", zero, original), ("paired", edit, donor)):
                forward(
                    f"{label}_{kind}_{context}",
                    context,
                    capture=True,
                    replacement=torch.tensor(value, dtype=torch.float32, device=adapter.device),
                    donor=target,
                    direction=v,
                )
    for context in ("high", "low"):
        forward(f"{context}_post_hook", context)
    return reports
