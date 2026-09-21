"""P1-015: bounded synthetic paired-coordinate and reverse replacement audit.

Launch in a fresh process with HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 and an unused run directory.
Only a synthetic pair and fixed synthetic directions; no science, generation or fallback.
"""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import torch

from steerability_is_not_mechanism.adapter_core import ForwardObservation
from steerability_is_not_mechanism.coordinate_check import (
    run_coordinate_check,
    synthetic_directions,
)
from steerability_is_not_mechanism.local_qwen import (
    configure_runtime,
    load_coordinate_adapter,
    read_coordinate_request,
)

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--request", type=Path, default=ROOT / "configs/local_coordinate.yaml")
parser.add_argument("--run-dir", type=Path, required=True)
args = parser.parse_args()
protocol_path = ROOT / "configs/local_model_engineering.yaml"
request, spec = read_coordinate_request(args.request, protocol_path)
args.run_dir.mkdir(parents=True, exist_ok=False)
record_path = args.run_dir / "run.json"
code_paths = sorted((ROOT / "src").rglob("*.py")) + [
    Path(__file__),
    args.request,
    protocol_path,
    ROOT / "uv.lock",
]
record = {
    "scope": request.scope,
    "command": sys.argv,
    "comparisons": [],
    "artifacts": {},
    "status": "starting",
    "started_at_utc": datetime.now(UTC).isoformat(),
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "code_config_hashes": {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in code_paths
    },
    "request": request.model_dump(),
    "protocol": spec.model_dump(),
    "python": platform.python_version(),
    "platform": platform.platform(),
    "loading_environment": {
        name: os.environ.get(name)
        for name in [
            "HF_HUB_OFFLINE",
            "TRANSFORMERS_OFFLINE",
            "PYTORCH_ENABLE_MPS_FALLBACK",
            "HF_DEACTIVATE_ASYNC_LOAD",
        ]
    },
    "packages": {
        name: importlib.metadata.version(name)
        for name in ["torch", "transformers", "tokenizers", "numpy", "safetensors", "accelerate"]
    },
    "forward_calls": 0,
    "generated_tokens": 0,
    "memory_before": subprocess.check_output(["memory_pressure"], text=True),
}


def save():
    record_path.write_text(json.dumps(record, indent=2) + "\n")


save()
try:
    device = configure_runtime(spec, request.device)
    record["selected_device"] = str(device)
    if device.type == "mps":
        recommended = torch.mps.recommended_max_memory()
        allocated = torch.mps.driver_allocated_memory()
        record["mps_before"] = {
            "recommended_bytes": recommended,
            "driver_allocated_bytes": allocated,
        }
        # Conservative storage estimate from all BF16 checkpoint entries, plus 512 MiB overhead.
        # This is a pre-load stopping rule, not a guarantee of memory fit.
        if recommended - allocated < 3_006_529_536 + 512 * 1024**2:
            raise RuntimeError("insufficient recommended MPS working-set capacity")
    record["status"] = "verifying_and_loading"
    save()
    print("Verifying and loading pinned Qwen on", device, flush=True)
    adapter, runtime = load_coordinate_adapter(
        request,
        spec,
        ROOT / "outputs/phase1/p1-005/tokenizer",
        ROOT / "models/Qwen3-0.6B" / spec.model.revision,
        device,
    )
    record["runtime"] = runtime
    ids = adapter.encode_decision_prompt(request.prompt)
    reference_path = ROOT / "outputs/phase1/p1-005/inspection.json"
    reference_bytes = reference_path.read_bytes()
    if (
        hashlib.sha256(reference_bytes).hexdigest()
        != "dc0a430e3d47c41e5bd2d03f4ae3eeecd2a4564c416c900d863dc1a4e1320aa2"
    ):
        raise ValueError("P1-005 token reference changed")
    reference = json.loads(reference_bytes)
    if ids.cpu().tolist() != [reference["input_ids"]]:
        raise ValueError("input IDs changed from the accepted tokenizer check")
    low_ids = adapter.encode_decision_prompt(request.low_prompt)
    inputs = {"high": ids, "low": low_ids}
    record["input_ids"] = {name: value.cpu().tolist() for name, value in inputs.items()}
    record["rendered_inputs"] = {
        name: adapter.tokenizer.decode(value.cpu().tolist()[0], skip_special_tokens=False)
        for name, value in inputs.items()
    }
    for label, v in synthetic_directions(spec.site.hidden_size).items():
        path = args.run_dir / f"direction_{label}.npy"
        np.save(path, v, allow_pickle=False)
        record["artifacts"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    save()

    def on_start(name: str) -> None:
        if record["forward_calls"] >= request.max_forward_calls:
            raise RuntimeError("forward budget exhausted")
        record["status"] = "running"
        record["current_pass"] = name
        record["forward_calls"] += 1
        save()
        print("Running", name, flush=True)

    def on_result(name: str, observation: ForwardObservation, report: dict) -> None:
        for label, tensor in [
            ("logits", observation.logits),
            ("activation", observation.activation),
            ("applied", observation.applied_replacement),
        ]:
            if tensor is not None:
                path = args.run_dir / f"{name}_{label}.npy"
                np.save(path, tensor.detach().cpu().numpy(), allow_pickle=False)
                record["artifacts"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        record["comparisons"].append(report)
        save()
        print(json.dumps(report), flush=True)

    run_coordinate_check(adapter, inputs, spec.checks, on_start, on_result)
    if device.type == "mps":
        record["mps_after"] = {
            "allocated_bytes": torch.mps.current_allocated_memory(),
            "driver_allocated_bytes": torch.mps.driver_allocated_memory(),
        }
    record["status"] = "passed"
    print("All 18 coordinate checks passed", flush=True)
except BaseException as error:
    record["status"] = "failed"
    record["error"] = f"{type(error).__name__}: {error}"
    raise
finally:
    record["finished_at_utc"] = datetime.now(UTC).isoformat()
    save()
    print("Record:", record_path, flush=True)
