"""Four fixed synthetic jobs, each recomputable without other jobs' activations."""

import io
import random
from collections.abc import Callable

import numpy as np
import torch

from .adapter_core import SinglePromptAdapterCore
from .coordinate_check import geometry_report, synthetic_directions
from .engineering_config import LocalEngineeringConfig
from .manifests import ManifestRow, shard_for
from .noop_check import checked_margin, compare_values


def synthetic_jobs() -> list[ManifestRow]:
    return sorted(
        [
            ManifestRow(
                run_id=f"synthetic-resume-{context}_{kind}",
                item_id="synthetic-2-plus-2",
                condition=context,
                intervention=kind,
                seed=1729,
            )
            for context in ("high", "low")
            for kind in ("capture", "edit")
        ],
        key=lambda row: row.run_id,
    )


def jobs_for_shard(shard: int) -> list[ManifestRow]:
    if shard not in (0, 1):
        raise ValueError("expected shard 0 or 1")
    return [row for row in synthetic_jobs() if shard_for(row.run_id, 2) == shard]


def unpack(payload: bytes) -> dict[str, np.ndarray]:
    with np.load(io.BytesIO(payload), allow_pickle=False) as data:
        return {name: data[name] for name in data.files}


def compute_job(
    row: ManifestRow,
    adapter: SinglePromptAdapterCore,
    inputs: dict[str, torch.Tensor],
    spec: LocalEngineeringConfig,
    before_forward: Callable[[], None],
) -> tuple[dict, bytes]:
    if row not in synthetic_jobs():
        raise ValueError("job is not in the fixed synthetic manifest")
    random.seed(row.seed)
    np.random.seed(row.seed)
    torch.manual_seed(row.seed)

    def observe(context, replacement=None):
        before_forward()
        obs = adapter.observe(inputs[context], adapter.layout.site, replacement)
        if any(m._forward_hooks or m._forward_pre_hooks for m in adapter.model.modules()):
            raise ValueError("hook leaked after job forward")
        if obs.activation is None:
            raise ValueError("job capture missing")
        return obs

    original = observe(row.condition)
    assert original.activation is not None
    arrays = {
        "logits": original.logits.cpu().numpy(),
        "activation": original.activation.cpu().numpy(),
    }
    metadata = {
        "row": row.model_dump(),
        "input_ids": {c: ids.cpu().tolist() for c, ids in inputs.items()},
        "hooks_clear": True,
    }
    output = original
    if row.intervention == "edit":
        donor = observe("low" if row.condition == "high" else "high")
        assert donor.activation is not None
        from .interventions import replace_coordinate

        v = synthetic_directions(adapter.layout.hidden_size)["alternating"]
        target = float(v @ donor.activation.cpu().double().numpy())
        proposal = replace_coordinate(original.activation.cpu().numpy(), v, target)
        replacement = torch.tensor(proposal, dtype=torch.float32, device=adapter.device)
        output = observe(row.condition, replacement)
        if output.activation is None or output.applied_replacement is None:
            raise ValueError("edit telemetry missing")
        geometry = geometry_report(
            original.activation.cpu().numpy(),
            output.applied_replacement.cpu().numpy(),
            donor.activation.cpu().numpy(),
            v,
            spec.checks,
        )
        capture_check = compare_values(output.activation, original.activation, spec.checks)
        if not (
            geometry["passed"]
            and capture_check["elements_pass"]
            and output.unedited_positions_exact is True
            and torch.equal(output.applied_replacement, replacement)
        ):
            raise ValueError("paired job geometry/capture/position check failed")
        metadata.update(
            geometry=geometry, capture_comparison=capture_check, unedited_positions_exact=True
        )
        arrays.update(
            logits=output.logits.cpu().numpy(),
            baseline_logits=original.logits.cpu().numpy(),
            donor=donor.activation.cpu().numpy(),
            applied=output.applied_replacement.cpu().numpy(),
            direction=v,
        )
    metadata["margin"] = checked_margin(output.logits, adapter.layout.option_ids)
    buffer = io.BytesIO()
    np.savez(buffer, allow_pickle=False, **arrays)
    return metadata, buffer.getvalue()
