"""P1-013: one explicitly scoped offline synthetic Qwen scoring pass.

Launch in a fresh process with HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 and an unused run directory.
No generation, capture/edit hooks, batches, pilot data or automatic device fallback.
"""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import torch

from steerability_is_not_mechanism.local_qwen import (
    configure_runtime,
    load_single_item_adapter,
    read_run_request,
)
from steerability_is_not_mechanism.metrics import answer_margin

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--request", type=Path, default=ROOT / "configs/local_single_item.yaml")
parser.add_argument("--run-dir", type=Path, required=True)
args = parser.parse_args()
protocol_path = ROOT / "configs/local_model_engineering.yaml"
request, spec = read_run_request(args.request, protocol_path)
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
    adapter, runtime = load_single_item_adapter(
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
    record["input_ids"] = ids.cpu().tolist()
    record["status"] = "single_forward"
    record["forward_calls"] = 1
    save()
    print("Running the one synthetic prompt; no generation or intervention", flush=True)
    logits = adapter.first_token_logits(ids).cpu().numpy()
    logits_path = args.run_dir / "final_token_logits.npy"
    np.save(logits_path, logits, allow_pickle=False)
    logp = torch.from_numpy(logits).double().log_softmax(-1)
    correct, endorsed = request.correct_token_id, request.user_token_id
    margin = float(logp[correct] - logp[endorsed])
    difference = float(logits[correct]) - float(logits[endorsed])
    independent_margin = answer_margin(logits, correct, endorsed)
    error = max(abs(margin - difference), abs(margin - independent_margin))
    scores = {
        "p_A": float(logp[correct].exp()),
        "p_B": float(logp[endorsed].exp()),
        "log_p_A": float(logp[correct]),
        "log_p_B": float(logp[endorsed]),
        "margin": margin,
        "raw_logit_difference": difference,
        "numpy_margin": independent_margin,
        "crosscheck_max_abs_error": error,
        "other_vocabulary_probability": float(1 - logp[correct].exp() - logp[endorsed].exp()),
        "top_token_id": int(np.argmax(logits)),
    }
    record["scores"] = scores
    record["logits_sha256"] = hashlib.sha256(logits_path.read_bytes()).hexdigest()
    if error > 1e-12:
        raise ValueError("first-token score cross-check failed")
    if device.type == "mps":
        record["mps_after"] = {
            "allocated_bytes": torch.mps.current_allocated_memory(),
            "driver_allocated_bytes": torch.mps.driver_allocated_memory(),
        }
    record["status"] = "passed"
    print(json.dumps(scores, indent=2), flush=True)
except Exception as error:
    record["status"] = "failed"
    record["error"] = f"{type(error).__name__}: {error}"
    raise
finally:
    record["finished_at_utc"] = datetime.now(UTC).isoformat()
    save()
    print("Record:", record_path, flush=True)
