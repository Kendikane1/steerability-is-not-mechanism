"""Remote bounded stage supervisor; explicit timeout and hard-kill resume audit."""

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from steerability_is_not_mechanism.process_control import kill_owned_tree, validate_worker_pid
from steerability_is_not_mechanism.process_logs import ProcessLog
from steerability_is_not_mechanism.resume_jobs import jobs_for_shard
from steerability_is_not_mechanism.shard_store import result_hash
from steerability_is_not_mechanism.sustained import atomic_json, compare_payloads

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--stage", choices=("single", "mechanics", "resume"), required=True)
parser.add_argument("--output-dir", type=Path, required=True)
args = parser.parse_args()
base = args.output_dir.resolve()
base.mkdir(parents=True, exist_ok=False)
report = {"status": "starting", "stage": args.stage, "attempts": []}


def save():
    atomic_json(base / "report.json", report)


def snapshot(directory):
    output = {}
    for path in sorted(directory.glob("*.sqlite")):
        db = sqlite3.connect(f"file:{path.as_posix()}?mode=rw", uri=True)
        try:
            assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            for key, meta, payload, digest in db.execute("SELECT * FROM results"):
                assert key not in output and result_hash(meta, payload) == digest
                output[key] = (json.loads(meta), payload, digest)
        finally:
            db.close()
    return output


def run(label, mode, group=None, shard=None, pause=None, incompatible=False, killed=False):
    attempt = base / label
    command = [
        sys.executable,
        str(ROOT / "notebooks/run_remote_engineering.py"),
        "--request",
        str(ROOT / f"configs/remote_{mode}.yaml"),
        "--attempt-dir",
        str(attempt),
    ]
    if group:
        command += ["--run-dir", str(base / group), "--shard", str(shard)]
    if pause:
        command += ["--pause-before-commit", pause]
    if incompatible:
        command += ["--incompatible"]
    env = os.environ.copy()
    env.update(
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        HF_DEACTIVATE_ASYNC_LOAD="1",
        CUBLAS_WORKSPACE_CONFIG=":4096:8",
    )
    proc = subprocess.Popen(
        command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    assert proc.stdout is not None
    capture = ProcessLog(proc.stdout, base / f"{label}.console.log")
    item = {"label": label, "command": command, "pid": proc.pid}
    report["attempts"].append(item)
    save()
    try:
        deadline = time.monotonic() + 210
        while proc.poll() is None:
            if time.monotonic() > deadline:
                raise TimeoutError("worker external deadline exceeded")
            ready = attempt / "ready.json"
            if pause and ready.exists():
                data = json.loads(ready.read_text())
                assert data["job"] == pause
                validate_worker_pid(proc.pid, data["pid"])
                item["worker_pid"] = data["pid"]
                journal = base / group / f"shard-{shard}.sqlite-journal"
                assert journal.stat().st_size > 0
                prior = snapshot(base / group)
                assert set(prior) == {jobs_for_shard(0)[0].run_id}
                item["committed_before_kill"] = {k: v[2] for k, v in prior.items()}
                item["journal_bytes"] = journal.stat().st_size
                kill_owned_tree(proc)  # Includes the Windows venv launcher and actual worker.
                item["intentional_termination"] = True
                break
            time.sleep(0.1)
        item["exit_code"] = proc.wait(timeout=10)
        state = json.loads((attempt / "attempt.json").read_text())
        item["state"] = state
        if killed:
            assert item.get("intentional_termination") and item["exit_code"] != 0
        elif incompatible:
            assert item["exit_code"] != 0 and "incompatible resume identity" in state.get(
                "error", ""
            )
            assert not state["model_loaded"] and state["forward_calls"] == 0
        else:
            assert item["exit_code"] == 0 and state["status"] == "passed", state.get("error")
        return state
    finally:
        if proc.poll() is None:
            kill_owned_tree(proc)
        capture.finish()
        item["console_sha256"] = hashlib.sha256(
            (base / f"{label}.console.log").read_bytes()
        ).hexdigest()
        save()


save()
try:
    if args.stage == "single":
        run("single", "single")
    elif args.stage == "mechanics":
        run("noop", "noop")
        run("coordinate", "coordinate")
    else:
        run("reference-0", "resume", "reference", 0)
        run("reference-1", "resume", "reference", 1)
        run("interrupted-0", "resume", "resumed", 0, jobs_for_shard(0)[1].run_id, killed=True)
        resumed = run("resumed-0", "resume", "resumed", 0)
        prior = report["attempts"][2]["committed_before_kill"]
        assert resumed["skipped"] == list(prior)
        run("resumed-1", "resume", "resumed", 1)
        actual, reference = snapshot(base / "resumed"), snapshot(base / "reference")
        assert set(actual) == set(reference)
        assert all(actual[k][2] == h for k, h in prior.items())
        report["comparisons"] = {k: compare_payloads(actual[k][1], reference[k][1]) for k in actual}
        replay = run("replay", "resume", "resumed", 0)
        assert not replay["model_loaded"] and replay["forward_calls"] == 0
        run("incompatible", "resume", "resumed", 0, incompatible=True)
        report["checkpoint_hashes"] = {
            str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in base.rglob("*.sqlite")
        }
    report["status"] = "passed"
except BaseException as error:
    report.update(status="failed", error=f"{type(error).__name__}: {error}")
    raise
finally:
    save()
    print(report["status"], report.get("error", ""), flush=True)
