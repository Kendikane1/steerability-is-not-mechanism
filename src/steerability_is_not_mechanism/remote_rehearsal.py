"""Separate CUDA rehearsal scope and predeclared endurance feasibility calculation."""

import hashlib
import math
from pathlib import Path

import yaml

from .engineering_config import load_engineering_config
from .local_qwen import CudaRehearsalRequest, _load_verified_adapter


def read_request(path: Path, protocol: Path):
    request = CudaRehearsalRequest.model_validate(yaml.safe_load(path.read_text()))
    if not request.execution_enabled:
        raise ValueError("CUDA rehearsal disabled")
    if hashlib.sha256(protocol.read_bytes()).hexdigest() != request.protocol_sha256:
        raise ValueError("protocol hash mismatch")
    return request, load_engineering_config(protocol)


def load_adapter(request, spec, root, device):
    if not isinstance(request, CudaRehearsalRequest):
        raise ValueError("CUDA rehearsal request required")
    return _load_verified_adapter(
        request,
        spec,
        root / "outputs/phase1/p1-005/tokenizer",
        root / "models/Qwen3-0.6B" / spec.model.revision,
        device,
    )


def source_hashes(root):
    paths = sorted((root / "src").rglob("*.py")) + [
        root / name
        for name in (
            "notebooks/run_remote_rehearsal.py",
            "notebooks/check_remote_rehearsal.py",
            "configs/remote_rehearsal.yaml",
            "configs/local_model_engineering.yaml",
            "docs/REMOTE_REHEARSAL_PROTOCOL.md",
            "docs/COMPACT_REHEARSAL_PROTOCOL.md",
            "uv.lock",
        )
    ]
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
    }


def feasibility(cycles, payload_per_cycle):
    if len(cycles) != 12 or any(not math.isfinite(x) or x <= 0 for x in cycles):
        raise ValueError("twelve finite positive cycle timings required")
    if not math.isfinite(payload_per_cycle) or payload_per_cycle <= 0:
        raise ValueError("invalid measured payload size")
    count = math.ceil(7200 / min(cycles[2:]) * 1.25)
    estimated = count * payload_per_cycle * 2 * 1.2 + 256 * 1024**2
    return {
        "cycle_seconds": cycles,
        "proposed_long_cycles": count,
        "estimated_long_output_bytes": estimated,
        "long_storage_feasible": estimated < 4 * 1024**3,
    }


def check_liveness(state, latest, now, started):
    if state is None:
        if now - started > 30:
            raise TimeoutError("worker startup exceeded 30 seconds")
        return
    if now - state["last_progress"] > 180:
        raise TimeoutError("no committed progress for 180 seconds")
    if latest is not None:
        if now - latest["time"] > 5 or latest["finished"] - latest["time"] > 5:
            raise RuntimeError("CUDA worker telemetry stale")
    elif state["status"] in {"loading", "computing", "paused"} and now - started > 30:
        raise RuntimeError("CUDA worker telemetry missing")
