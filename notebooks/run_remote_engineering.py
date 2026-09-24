"""Bounded CUDA worker: single score, no-op, coordinate or one four-job resume shard."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from steerability_is_not_mechanism.coordinate_check import run_coordinate_check
from steerability_is_not_mechanism.noop_check import checked_margin, run_noop_check
from steerability_is_not_mechanism.remote_cuda import (
    CudaMonitor,
    configure_cuda,
    load_cuda_adapter,
    read_cuda_request,
)
from steerability_is_not_mechanism.resume_jobs import compute_job, jobs_for_shard, synthetic_jobs
from steerability_is_not_mechanism.shard_store import ShardStore
from steerability_is_not_mechanism.sustained import atomic_json

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--request", type=Path, required=True)
parser.add_argument("--attempt-dir", type=Path, required=True)
parser.add_argument("--run-dir", type=Path)
parser.add_argument("--shard", type=int, choices=(0, 1))
parser.add_argument("--pause-before-commit", choices=[r.run_id for r in synthetic_jobs()])
parser.add_argument("--incompatible", action="store_true")
args = parser.parse_args()
args.attempt_dir.mkdir(parents=True, exist_ok=False)
state = {
    "utc": datetime.now(UTC).isoformat(),
    "pid": os.getpid(),
    "status": "starting",
    "forward_calls": 0,
    "model_loaded": False,
    "comparisons": [],
    "artifacts": {},
    "executed": [],
    "skipped": [],
}
monitor = store = adapter = None
inputs = {}


def save():
    atomic_json(args.attempt_dir / "attempt.json", state)


def array(name, value):
    path = args.attempt_dir / (name + ".npy")
    np.save(path, value, allow_pickle=False)
    state["artifacts"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()


save()
try:
    request, spec = read_cuda_request(args.request, ROOT / "configs/local_model_engineering.yaml")
    paths = sorted((ROOT / "src").rglob("*.py")) + [
        Path(__file__),
        args.request,
        ROOT / "uv.lock",
        ROOT / "configs/local_model_engineering.yaml",
    ]
    device = configure_cuda(spec)
    identity = {
        "request": request.model_dump(),
        "protocol": spec.model_dump(),
        "device": str(device),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "sqlite": sqlite3.sqlite_version,
        "source_hashes": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
        },
        "environment": {
            k: os.environ.get(k)
            for k in [
                "HF_HUB_OFFLINE",
                "TRANSFORMERS_OFFLINE",
                "HF_DEACTIVATE_ASYNC_LOAD",
                "CUBLAS_WORKSPACE_CONFIG",
            ]
        },
        "packages": {
            n: importlib.metadata.version(n)
            for n in ["torch", "transformers", "tokenizers", "numpy", "safetensors", "accelerate"]
        },
    }
    if args.incompatible:
        identity["device"] = "deliberately_incompatible"
    state["identity"] = identity
    save()

    def load():
        global adapter, inputs, monitor
        if adapter is None:
            monitor = CudaMonitor(args.attempt_dir, ROOT)
            state["status"] = "loading"
            save()
            adapter, runtime = load_cuda_adapter(request, spec, ROOT, device)
            state.update(model_loaded=True, runtime=runtime)
            inputs = {
                "high": adapter.encode_decision_prompt(request.prompt),
                "low": adapter.encode_decision_prompt(request.low_prompt),
            }
            ref = ROOT / "outputs/phase1/p1-005/inspection.json"
            if (
                hashlib.sha256(ref.read_bytes()).hexdigest()
                != "dc0a430e3d47c41e5bd2d03f4ae3eeecd2a4564c416c900d863dc1a4e1320aa2"
            ):
                raise ValueError("token reference changed")
            if inputs["high"].cpu().tolist() != [json.loads(ref.read_text())["input_ids"]]:
                raise ValueError("token IDs changed")
            state["input_ids"] = {k: v.cpu().tolist() for k, v in inputs.items()}
            state["resource_after_load"] = monitor.sample()
            save()
        return adapter

    def start(name="job"):
        if state["forward_calls"] >= request.max_forward_calls:
            raise RuntimeError("CUDA forward budget exhausted")
        assert monitor is not None
        monitor.sample()
        state.update(
            status="computing", current_pass=name, forward_calls=state["forward_calls"] + 1
        )
        save()

    def result(name, observation, comparison):
        for suffix, value in [
            ("logits", observation.logits),
            ("activation", observation.activation),
            ("applied", observation.applied_replacement),
        ]:
            if value is not None:
                array(name + "_" + suffix, value.detach().cpu().numpy())
        state["comparisons"].append(comparison)
        save()

    if request.mode == "resume":
        if args.run_dir is None or args.shard is None:
            raise ValueError("resume requires run directory and shard")
        rows = jobs_for_shard(args.shard)
        identity.update(manifest=[r.model_dump() for r in synthetic_jobs()], shard=args.shard)
        store = ShardStore(
            args.run_dir / f"shard-{args.shard}.sqlite", identity, [r.run_id for r in rows]
        )
        state["completed_at_start"] = {k: v[2] for k, v in store.completed().items()}
        save()
        if args.pause_before_commit and args.pause_before_commit not in [r.run_id for r in rows]:
            raise ValueError("pause target not in shard")
        for row in rows:
            state["current_job"] = row.run_id
            save()

            def compute(row=row):
                a = load()
                return compute_job(row, a, inputs, spec, start)

            def before_commit(row=row):
                if row.run_id == args.pause_before_commit:
                    state["status"] = "paused"
                    save()
                    atomic_json(
                        args.attempt_dir / "ready.json", {"pid": os.getpid(), "job": row.run_id}
                    )
                    time.sleep(30)
                    raise TimeoutError("supervisor did not terminate paused worker")

            done = store.execute(row.run_id, compute, before_commit)
            state["executed" if done else "skipped"].append(row.run_id)
            save()
        state["completed_at_end"] = {k: v[2] for k, v in store.completed().items()}
    elif request.mode == "single":
        a = load()
        start("single")
        logits = a.first_token_logits(inputs["high"])
        array("single_logits", logits.cpu().numpy())
        margin = checked_margin(logits, a.layout.option_ids)
        logp = logits.cpu().double().log_softmax(-1)
        state["scores"] = {
            "p_A": float(logp[32].exp()),
            "p_B": float(logp[33].exp()),
            "margin": margin,
            "top_token_id": int(logits.argmax()),
        }
    elif request.mode == "noop":
        a = load()
        run_noop_check(a, inputs["high"], spec.checks, start, result)
    else:
        a = load()
        run_coordinate_check(a, inputs, spec.checks, start, result)
    if monitor:
        state["resource_after"] = monitor.sample()
    state["status"] = "passed"
except BaseException as error:
    state.update(status="failed", error=f"{type(error).__name__}: {error}")
    raise
finally:
    if store:
        store.close()
    if monitor:
        monitor.close()
    state["finished_utc"] = datetime.now(UTC).isoformat()
    save()
    print(state["status"], state.get("error", ""), flush=True)
