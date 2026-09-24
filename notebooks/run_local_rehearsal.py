"""P1-020 worker: 12 fixed cycles, sequential shards, one model per process."""

import argparse
import importlib.metadata
import os
import platform
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

from steerability_is_not_mechanism.local_qwen import (
    configure_runtime,
    load_rehearsal_adapter,
    read_rehearsal_request,
)
from steerability_is_not_mechanism.manifests import ManifestRow
from steerability_is_not_mechanism.resume_jobs import compute_job
from steerability_is_not_mechanism.shard_store import ShardStore
from steerability_is_not_mechanism.sustained import (
    MemorySampler,
    atomic_json,
    compare_payloads,
    content_hashes,
    rehearsal_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--run-dir", type=Path, required=True)
parser.add_argument("--attempt-dir", type=Path, required=True)
parser.add_argument("--pause-midpoint", action="store_true")
parser.add_argument("--incompatible", action="store_true")
args = parser.parse_args()
args.attempt_dir.mkdir(parents=True, exist_ok=False)
state = {
    "utc": datetime.now(UTC).isoformat(),
    "status": "starting",
    "forward_calls": 0,
    "model_loaded": False,
    "executed": [],
    "skipped": [],
    "last_progress": time.monotonic(),
}


def save():
    atomic_json(args.attempt_dir / "attempt.json", state)


adapter = inputs = monitor = store = None
monitor_seconds = 0.0
save()
try:
    request, spec = read_rehearsal_request(
        ROOT / "configs/local_rehearsal.yaml", ROOT / "configs/local_model_engineering.yaml"
    )
    device = configure_runtime(spec, request.device)
    manifest = rehearsal_manifest()
    identity = {
        "request": request.model_dump(),
        "manifest": manifest,
        "source_hashes": content_hashes(ROOT),
        "device": str(device),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "sqlite": sqlite3.sqlite_version,
        "packages": {
            k: importlib.metadata.version(k)
            for k in ["torch", "transformers", "numpy", "tokenizers", "safetensors", "accelerate"]
        },
        "environment": {
            k: os.environ.get(k)
            for k in [
                "HF_HUB_OFFLINE",
                "TRANSFORMERS_OFFLINE",
                "HF_DEACTIVATE_ASYNC_LOAD",
                "PYTORCH_ENABLE_MPS_FALLBACK",
            ]
        },
    }
    if args.incompatible:
        identity["device"] = "deliberately-incompatible"
    state["identity"] = identity
    save()
    fixtures = {}
    for shard in range(3):
        jobs = [r for r in manifest if r["shard"] == shard]
        store = ShardStore(
            args.run_dir / f"shard-{shard}.sqlite", identity, [r["id"] for r in jobs]
        )
        # Rebuild only four reference fixtures from committed records after restart.
        for _, (metadata, payload, _) in store.completed().items():
            fixtures.setdefault(metadata["fixture_id"], payload)
        for job in jobs:
            state["current_job"] = job["id"]
            save()

            def before_forward():
                global monitor_seconds
                overhead_started = time.monotonic()
                assert monitor is not None
                monitor.check("before_forward")
                if state["forward_calls"] >= request.max_forward_calls:
                    raise RuntimeError("rehearsal forward budget exhausted")
                state["forward_calls"] += 1
                save()
                monitor_seconds += time.monotonic() - overhead_started

            def compute(job=job):
                global adapter, inputs, monitor, monitor_seconds
                if adapter is None:
                    state["status"] = "loading"
                    save()
                    monitor = MemorySampler(args.attempt_dir, device)
                    monitor.check("before_load")
                    adapter, runtime = load_rehearsal_adapter(
                        request,
                        spec,
                        ROOT / "outputs/phase1/p1-005/tokenizer",
                        ROOT / "models/Qwen3-0.6B" / spec.model.revision,
                        device,
                    )
                    state.update(model_loaded=True, runtime=runtime, loaded_at=time.monotonic())
                    inputs = {
                        "high": adapter.encode_decision_prompt(request.prompt),
                        "low": adapter.encode_decision_prompt(request.low_prompt),
                    }
                    monitor.check("after_load")
                state["status"] = "computing"
                save()
                monitor_seconds = 0.0
                started = time.monotonic()
                assert inputs is not None
                row = ManifestRow.model_validate(job["fixture"])
                metadata, payload = compute_job(row, adapter, inputs, spec, before_forward)
                elapsed = time.monotonic() - started - monitor_seconds
                assert monitor is not None
                monitor.check("after_job")
                reference = fixtures.setdefault(row.run_id, payload)
                metadata.update(
                    comparison=compare_payloads(payload, reference),
                    fixture_id=row.run_id,
                    unique_id=job["id"],
                    cycle=job["cycle"],
                    active_seconds=elapsed,
                    boundary_monitor_seconds=monitor_seconds,
                )
                return metadata, payload

            def before_commit(job=job, shard=shard):
                if args.pause_midpoint and job["id"] == manifest[24]["id"]:
                    state["status"] = "paused"
                    save()
                    atomic_json(
                        args.attempt_dir / "ready.json",
                        {"pid": os.getpid(), "job": job["id"], "shard": shard},
                    )
                    time.sleep(30)
                    raise TimeoutError("fault supervisor did not kill worker")

            done = store.execute(job["id"], compute, before_commit)
            state["executed" if done else "skipped"].append(job["id"])
            state["last_progress"] = time.monotonic()
            save()
        store.close()
        store = None
    state["status"] = "passed"
except BaseException as error:
    state.update(status="failed", error=f"{type(error).__name__}: {error}")
    raise
finally:
    if store is not None:
        store.close()
    if monitor is not None:
        monitor.close()
    state["finished_utc"] = datetime.now(UTC).isoformat()
    save()
