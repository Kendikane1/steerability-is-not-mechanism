"""P1-016: one resumable local shard; fixed synthetic jobs only, no scientific execution."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import torch

from steerability_is_not_mechanism.local_qwen import (
    configure_runtime,
    load_resume_adapter,
    read_resume_request,
)
from steerability_is_not_mechanism.manifests import manifest_sha256
from steerability_is_not_mechanism.resume_jobs import compute_job, jobs_for_shard, synthetic_jobs
from steerability_is_not_mechanism.shard_store import ShardStore

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--request", type=Path, default=ROOT / "configs/local_resume.yaml")
parser.add_argument("--run-dir", type=Path, required=True)
parser.add_argument("--attempt-dir", type=Path, required=True)
parser.add_argument("--shard", type=int, choices=(0, 1), required=True)
parser.add_argument("--pause-before-commit", choices=[r.run_id for r in synthetic_jobs()])
args = parser.parse_args()
request, spec = read_resume_request(args.request, ROOT / "configs/local_model_engineering.yaml")
args.attempt_dir.mkdir(parents=True, exist_ok=False)
record_path = args.attempt_dir / "attempt.json"
record = {
    "started_at_utc": datetime.now(UTC).isoformat(),
    "command": sys.argv,
    "status": "starting",
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "forward_calls": 0,
    "model_loaded": False,
    "executed": [],
    "skipped": [],
}


def save():
    record_path.write_text(json.dumps(record, indent=2) + "\n")


store = None
adapter = None
inputs = None
save()
try:
    device = configure_runtime(spec, request.device)
    if os.environ.get("HF_DEACTIVATE_ASYNC_LOAD") != "1":
        raise ValueError("sequential loading required")
    paths = sorted((ROOT / "src").rglob("*.py")) + [
        Path(__file__),
        ROOT / "uv.lock",
        ROOT / "configs/local_model_engineering.yaml",
    ]
    # Request values, not filename, define identity; an alternate path cannot bypass comparison.
    identity = {
        "scope": request.scope,
        "request": request.model_dump(),
        "protocol": spec.model_dump(),
        "manifest": [r.model_dump() for r in synthetic_jobs()],
        "manifest_sha256": manifest_sha256(synthetic_jobs()),
        "source_hashes": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
        },
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "device": str(device),
        "sqlite": sqlite3.sqlite_version,
        "packages": {
            n: importlib.metadata.version(n)
            for n in ["torch", "transformers", "tokenizers", "numpy", "safetensors", "accelerate"]
        },
        "environment": {
            n: os.environ.get(n)
            for n in [
                "HF_HUB_OFFLINE",
                "TRANSFORMERS_OFFLINE",
                "PYTORCH_ENABLE_MPS_FALLBACK",
                "HF_DEACTIVATE_ASYNC_LOAD",
            ]
        },
        "shard": args.shard,
    }
    record["identity"] = identity
    save()
    rows = jobs_for_shard(args.shard)
    if args.pause_before_commit and args.pause_before_commit not in [r.run_id for r in rows]:
        raise ValueError("pause target not in selected shard")
    store = ShardStore(
        args.run_dir / f"shard-{args.shard}.sqlite", identity, [r.run_id for r in rows]
    )
    record["completed_at_start"] = {k: v[2] for k, v in store.completed().items()}
    save()

    def before_forward():
        if record["forward_calls"] >= request.max_forward_calls:
            raise RuntimeError("forward budget exhausted")
        record["forward_calls"] += 1
        save()

    def compute(row):
        global adapter, inputs
        record["status"] = "computing"
        record["current_job"] = row.run_id
        save()
        if adapter is None:
            if (
                device.type == "mps"
                and torch.mps.recommended_max_memory() - torch.mps.driver_allocated_memory()
                < 3_006_529_536 + 512 * 1024**2
            ):
                raise RuntimeError("insufficient recommended MPS capacity")
            adapter, runtime = load_resume_adapter(
                request,
                spec,
                ROOT / "outputs/phase1/p1-005/tokenizer",
                ROOT / "models/Qwen3-0.6B" / spec.model.revision,
                device,
            )
            record["model_loaded"] = True
            record["runtime"] = runtime
            inputs = {
                "high": adapter.encode_decision_prompt(request.prompt),
                "low": adapter.encode_decision_prompt(request.low_prompt),
            }
            save()
        assert inputs is not None
        return compute_job(row, adapter, inputs, spec, before_forward)

    def before_commit():
        if record.get("current_job") == args.pause_before_commit:
            record["status"] = "paused_before_commit"
            save()
            (args.attempt_dir / "ready.json").write_text(
                json.dumps({"pid": os.getpid(), "job": args.pause_before_commit})
            )
            # Supervisor SIGKILLs this owned worker; deadline avoids an orphaned indefinite wait.
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                time.sleep(0.1)
            raise TimeoutError("fault-injection supervisor did not terminate worker")

    for row in rows:
        completed = store.execute(row.run_id, lambda row=row: compute(row), before_commit)
        record["executed" if completed else "skipped"].append(row.run_id)
        save()
        print("committed" if completed else "skipped", row.run_id, flush=True)
    record["completed_at_end"] = {k: v[2] for k, v in store.completed().items()}
    record["status"] = "passed"
except BaseException as error:
    record["status"] = "failed"
    record["error"] = f"{type(error).__name__}: {error}"
    raise
finally:
    if store is not None:
        store.close()
    record["finished_at_utc"] = datetime.now(UTC).isoformat()
    save()
