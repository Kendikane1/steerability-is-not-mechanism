"""P1-027 CUDA worker: fixed endurance cycles, sequential shards, one model per process."""

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

from steerability_is_not_mechanism.compact_store import CompactShardStore, file_hash
from steerability_is_not_mechanism.long_memory import LongMonitor
from steerability_is_not_mechanism.long_run import (
    MANIFEST_SHA256,
    MIDPOINT,
    WALL_SECONDS,
    batches,
    load_adapter,
    source_hashes,
)
from steerability_is_not_mechanism.long_run import request as read_request
from steerability_is_not_mechanism.manifests import ManifestRow
from steerability_is_not_mechanism.remote_cuda import configure_cuda
from steerability_is_not_mechanism.resume_jobs import compute_job
from steerability_is_not_mechanism.sustained import (
    atomic_json,
    compare_payloads,
)

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--run-dir", type=Path, required=True)
parser.add_argument("--attempt-dir", type=Path, required=True)
parser.add_argument("--pause-midpoint", action="store_true")
parser.add_argument("--incompatible", action="store_true")
parser.add_argument("--manifest", type=Path, required=True)
args = parser.parse_args()
args.attempt_dir.mkdir(parents=True, exist_ok=False)
state = {
    "utc": datetime.now(UTC).isoformat(),
    "status": "starting",
    "forward_calls": 0,
    "model_loaded": False,
    "executed": 0,
    "skipped": 0,
    "last_progress": time.monotonic(),
}


def save():
    atomic_json(args.attempt_dir / "attempt.json", state)


adapter = inputs = monitor = store = None
monitor_seconds = 0.0
save()
try:
    request, spec = read_request(ROOT)
    if file_hash(args.manifest) != MANIFEST_SHA256:
        raise ValueError("fixed manifest hash mismatch")
    device = configure_cuda(spec)
    identity = {
        "storage": "compact-sustained-v1",
        "request": request.model_dump(),
        "manifest_sha256": file_hash(args.manifest),
        "source_hashes": source_hashes(ROOT),
        "device": str(device),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "sqlite": sqlite3.sqlite_version,
        "packages": {
            k: importlib.metadata.version(k)
            for k in [
                "torch",
                "transformers",
                "numpy",
                "tokenizers",
                "safetensors",
                "accelerate",
                "psutil",
            ]
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
    }
    if args.incompatible:
        identity["device"] = "deliberately-incompatible"
    state["identity"] = identity
    save()
    fixtures = {}
    for jobs in batches(args.manifest):
        shard = jobs[0]["shard"]
        store = CompactShardStore(
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
                monitor.sample()
                if state["forward_calls"] >= request.max_forward_calls:
                    raise RuntimeError("sustained forward budget exhausted")
                state["forward_calls"] += 1
                save()
                monitor_seconds += time.monotonic() - overhead_started

            def compute(job=job):
                global adapter, inputs, monitor, monitor_seconds
                if adapter is None:
                    state["status"] = "loading"
                    save()
                    monitor = LongMonitor(args.attempt_dir, ROOT, seconds=WALL_SECONDS)
                    adapter, runtime = load_adapter(request, spec, ROOT, device)
                    state.update(model_loaded=True, runtime=runtime, loaded_at=time.monotonic())
                    monitor.loaded_at = state["loaded_at"]
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
                    monitor.sample()
                state["status"] = "computing"
                save()
                monitor_seconds = 0.0
                started = time.monotonic()
                assert inputs is not None
                row = ManifestRow.model_validate(job["fixture"])
                metadata, payload = compute_job(row, adapter, inputs, spec, before_forward)
                elapsed = time.monotonic() - started - monitor_seconds
                assert monitor is not None
                monitor.sample()
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
                if args.pause_midpoint and job["index"] == MIDPOINT:
                    assert monitor is not None
                    monitor.finish_growth()
                    state["status"] = "paused"
                    save()
                    atomic_json(
                        args.attempt_dir / "ready.json",
                        {"pid": os.getpid(), "job": job["id"], "shard": shard},
                    )
                    time.sleep(300)
                    raise TimeoutError("fault supervisor did not kill worker")

            done = store.execute(job["id"], compute, before_commit)
            state["executed" if done else "skipped"] += 1
            state["last_progress"] = time.monotonic()
            save()
        store.close()
        store = None
    if monitor is not None:
        monitor.finish_growth()
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
