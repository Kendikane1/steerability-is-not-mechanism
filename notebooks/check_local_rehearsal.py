"""Supervise the fixed rehearsal and stop on resource or correctness failures."""

import argparse
import hashlib
import json
import math
import os
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from steerability_is_not_mechanism.process_logs import ProcessLog
from steerability_is_not_mechanism.resource_guard import GIB, check_system, read_system
from steerability_is_not_mechanism.shard_store import result_hash
from steerability_is_not_mechanism.sustained import (
    atomic_json,
    compare_payloads,
    content_hashes,
    rehearsal_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output-dir", type=Path, required=True)
args = parser.parse_args()
base = args.output_dir.resolve()
base.mkdir(parents=True, exist_ok=False)
report = {
    "utc": datetime.now(UTC).isoformat(),
    "status": "starting",
    "attempts": [],
    "pressure_policy": "warn_record_critical_stop",
    "source_hashes": content_hashes(ROOT),
    "manifest": rehearsal_manifest(),
}


def save():
    atomic_json(base / "report.json", report)


def size():
    return sum(p.stat().st_size for p in base.rglob("*") if p.is_file())


def snapshot(folder):
    rows = {}
    for path in sorted(folder.glob("*.sqlite")):
        db = sqlite3.connect(f"file:{path}?mode=rw", uri=True)
        try:
            assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            for key, meta, payload, digest in db.execute("SELECT * FROM results"):
                if key in rows or result_hash(meta, payload) != digest:
                    raise ValueError("duplicate/corrupt checkpoint row")
                rows[key] = (json.loads(meta), payload, digest)
        finally:
            db.close()
    return rows


def run(label, group, deadline, pause=False, incompatible=False, expected=0):
    attempt = base / label
    command = [
        sys.executable,
        str(ROOT / "notebooks/run_local_rehearsal.py"),
        "--run-dir",
        str(base / group),
        "--attempt-dir",
        str(attempt),
    ]
    if pause:
        command.append("--pause-midpoint")
    if incompatible:
        command.append("--incompatible")
    item = {"label": label, "command": command, "expected_exit": expected}
    report["attempts"].append(item)
    save()
    env = os.environ.copy()
    env.update(
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        HF_DEACTIVATE_ASYNC_LOAD="1",
        PYTORCH_ENABLE_MPS_FALLBACK="0",
    )
    start = time.monotonic()
    proc = subprocess.Popen(
        command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    assert proc.stdout is not None
    capture = ProcessLog(proc.stdout, base / f"{label}.console.log")
    try:
        while proc.poll() is None:
            reading = read_system(base)
            with (base / "system.jsonl").open("a") as log:
                log.write(json.dumps({"attempt": label, **reading.as_dict()}) + "\n")
            check_system(
                reading,
                now=time.monotonic(),
                baseline_swap=baseline.swap_bytes,
                startup=False,
                output_bytes=size(),
                allow_warning=True,
            )
            now = time.monotonic()
            if now > deadline:
                raise TimeoutError("arm exceeded frozen deadline")
            monitor_error = attempt / "monitor_error.json"
            if monitor_error.exists():
                raise RuntimeError(monitor_error.read_text())
            memory = attempt / "memory_latest.json"
            if memory.exists():
                latest = json.loads(memory.read_text())
                if now - latest["started"] > 5:
                    raise RuntimeError("worker memory telemetry stale")
            state_path = attempt / "attempt.json"
            if state_path.exists():
                state = json.loads(state_path.read_text())
                if now - state["last_progress"] > 180:
                    raise TimeoutError("no progress for 180 seconds")
                if (
                    state["status"] in {"loading", "computing"}
                    and not memory.exists()
                    and now - start > 30
                ):
                    raise RuntimeError("worker memory telemetry missing")
            elif now - start > 30:
                raise TimeoutError("worker startup exceeded 30 seconds")
            ready_path = attempt / "ready.json"
            if pause and ready_path.exists():
                ready = json.loads(ready_path.read_text())
                assert ready["pid"] == proc.pid and ready["job"] == rehearsal_manifest()[24]["id"]
                journal = base / group / f"shard-{ready['shard']}.sqlite-journal"
                assert journal.stat().st_size > 0
                committed = snapshot(base / group)
                assert set(committed) == {r["id"] for r in rehearsal_manifest()[:24]}
                item["committed_before_kill"] = {k: v[2] for k, v in committed.items()}
                item["journal_bytes"] = journal.stat().st_size
                proc.kill()
                break
            time.sleep(1)
        code = proc.wait(timeout=5)
        item["exit_code"] = code
        state = json.loads((attempt / "attempt.json").read_text())
        item["state"] = state
        if code != expected:
            raise RuntimeError(f"unexpected worker exit {code}: {state.get('error')}")
        return state
    except BaseException as error:
        item["error"] = f"{type(error).__name__}: {error}"
        attempt.mkdir(exist_ok=True)
        (attempt / "stop").touch()
        if proc.poll() is None:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        item["exit_code"] = proc.returncode
        raise
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        capture.finish()
        item["console_sha256"] = hashlib.sha256(
            (base / f"{label}.console.log").read_bytes()
        ).hexdigest()
        save()


save()
try:
    baseline = read_system(base)
    report["baseline"] = baseline.as_dict()
    check_system(
        baseline,
        now=time.monotonic(),
        baseline_swap=baseline.swap_bytes,
        startup=True,
        allow_warning=True,
    )
    save()
    reference = run("reference", "reference-db", time.monotonic() + 600)
    deadline = time.monotonic() + 600
    run("interrupted", "resumed-db", deadline, pause=True, expected=-9)
    resumed = run("resumed", "resumed-db", deadline)
    ref, actual = snapshot(base / "reference-db"), snapshot(base / "resumed-db")
    assert set(ref) == set(actual) == {r["id"] for r in rehearsal_manifest()}
    prior = report["attempts"][1]["committed_before_kill"]
    assert set(resumed["skipped"]) == set(prior)
    assert all(actual[k][2] == h for k, h in prior.items())
    report["comparisons"] = {k: compare_payloads(actual[k][1], ref[k][1]) for k in ref}
    replay = run("replay", "resumed-db", time.monotonic() + 180)
    assert not replay["model_loaded"] and replay["forward_calls"] == 0
    bad = run("incompatible", "resumed-db", time.monotonic() + 180, incompatible=True, expected=1)
    assert not bad["model_loaded"] and bad["forward_calls"] == 0
    assert "incompatible resume identity" in bad["error"]
    cycles = [
        sum(v[0]["active_seconds"] for v in ref.values() if v[0]["cycle"] == i) for i in range(12)
    ]
    # Predeclared rehearsal timing warm-up: discard the first two cycles (not long-run memory warm-up).
    count = math.ceil(7200 / min(cycles[2:]) * 1.25)
    payload_per_cycle = sum(len(v[1]) for v in ref.values()) / 12
    estimated = count * payload_per_cycle * 2 * 1.2 + 256 * 1024**2
    report.update(
        status="rehearsal_passed",
        cycle_seconds=cycles,
        proposed_long_cycles=count,
        estimated_long_output_bytes=estimated,
        long_storage_feasible=estimated < 4 * GIB,
        checkpoint_hashes={
            str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in base.rglob("*.sqlite")
        },
    )
except BaseException as error:
    report.update(status="stopped", error=f"{type(error).__name__}: {error}")
    raise
finally:
    report["finished_utc"] = datetime.now(UTC).isoformat()
    save()
    print(report["status"], report.get("error", ""), flush=True)
