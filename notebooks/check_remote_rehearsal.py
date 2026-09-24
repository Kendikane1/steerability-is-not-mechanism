"""Supervise the fixed rehearsal and stop on resource or correctness failures."""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from steerability_is_not_mechanism.compact_store import file_hash
from steerability_is_not_mechanism.compact_store import snapshot as compact_snapshot
from steerability_is_not_mechanism.process_control import kill_owned_tree, validate_worker_pid
from steerability_is_not_mechanism.process_logs import ProcessLog
from steerability_is_not_mechanism.remote_cuda import GIB, windows_memory
from steerability_is_not_mechanism.remote_rehearsal import (
    check_liveness,
    feasibility,
    source_hashes,
)
from steerability_is_not_mechanism.shard_store import result_hash
from steerability_is_not_mechanism.sustained import (
    atomic_json,
    compare_payloads,
    rehearsal_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output-dir", type=Path, required=True)
parser.add_argument("--compact", action="store_true")
args = parser.parse_args()
base = args.output_dir.resolve()
base.mkdir(parents=True, exist_ok=False)
report = {
    "storage": "compact-v1" if args.compact else "original-v1",
    "utc": datetime.now(UTC).isoformat(),
    "status": "starting",
    "attempts": [],
    "source_hashes": source_hashes(ROOT),
    "manifest": rehearsal_manifest(),
}


def save():
    atomic_json(base / "report.json", report)


def size():
    total = 0
    for path in base.rglob("*"):
        try:
            if path.is_file():
                total += path.stat().st_size
        except FileNotFoundError:
            pass  # SQLite removes rollback journals after commit.
    return total


def snapshot(folder):
    if args.compact:
        identity = json.loads(
            (
                base
                / ("reference" if folder.name == "reference-db" else "interrupted")
                / "attempt.json"
            ).read_text()
        )["identity"]
        return compact_snapshot(folder, identity)
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
        str(ROOT / "notebooks/run_remote_rehearsal.py"),
        "--run-dir",
        str(base / group),
        "--attempt-dir",
        str(attempt),
    ]
    if args.compact:
        command.append("--compact")
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
        CUBLAS_WORKSPACE_CONFIG=":4096:8",
    )
    start = time.monotonic()
    proc = subprocess.Popen(
        command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    assert proc.stdout is not None
    capture = ProcessLog(proc.stdout, base / f"{label}.console.log")
    try:
        while proc.poll() is None:
            now = time.monotonic()
            memory_status = windows_memory()
            disk_free = shutil.disk_usage(base).free
            with (base / "system.jsonl").open("a") as log:
                log.write(
                    json.dumps(
                        {
                            "attempt": label,
                            "time": now,
                            "ram": memory_status,
                            "disk_free": disk_free,
                        }
                    )
                    + "\n"
                )
            if disk_free < 20 * GIB or size() >= 4 * GIB:
                raise RuntimeError("rehearsal disk/output limit exceeded")
            if (
                memory_status["avail_phys"] < GIB // 2
                or memory_status["avail_commit"] < GIB // 2
                or memory_status["load"] >= 95
            ):
                raise RuntimeError("Windows RAM/commit reserve breached")
            if now > deadline:
                raise TimeoutError("arm exceeded frozen deadline")
            abort = attempt / "abort.json"
            if abort.exists():
                raise RuntimeError(abort.read_text())
            latest_path = attempt / "resources_latest.json"
            state_path = attempt / "attempt.json"
            state = json.loads(state_path.read_text()) if state_path.exists() else None
            latest = json.loads(latest_path.read_text()) if latest_path.exists() else None
            check_liveness(state, latest, now, start)
            ready_path = attempt / "ready.json"
            if pause and ready_path.exists():
                ready = json.loads(ready_path.read_text())
                assert ready["job"] == rehearsal_manifest()[24]["id"]
                validate_worker_pid(proc.pid, ready["pid"])
                item["worker_pid"] = ready["pid"]
                journal = base / group / f"shard-{ready['shard']}.sqlite-journal"
                assert journal.stat().st_size > 0
                committed = snapshot(base / group)
                assert set(committed) == {r["id"] for r in rehearsal_manifest()[:24]}
                item["committed_before_kill"] = {k: v[2] for k, v in committed.items()}
                item["journal_bytes"] = journal.stat().st_size
                kill_owned_tree(proc)
                item["intentional_termination"] = True
                break
            time.sleep(1)
        code = proc.wait(timeout=5)
        item["exit_code"] = code
        state = json.loads((attempt / "attempt.json").read_text())
        item["state"] = state
        if (pause and not (item.get("intentional_termination") and code != 0)) or (
            not pause and code != expected
        ):
            raise RuntimeError(f"unexpected worker exit {code}: {state.get('error')}")
        return state
    except BaseException as error:
        item["error"] = f"{type(error).__name__}: {error}"
        if proc.poll() is None:
            kill_owned_tree(proc)
        item["exit_code"] = proc.returncode
        state_path = attempt / "attempt.json"
        if state_path.exists():
            item["state"] = json.loads(state_path.read_text())
        raise
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
    baseline = windows_memory()
    report["baseline"] = baseline
    if (
        baseline["avail_phys"] < GIB
        or baseline["avail_commit"] < GIB
        or baseline["load"] >= 95
        or shutil.disk_usage(base).free < 20 * GIB
    ):
        raise RuntimeError("Windows startup reserve breached")
    save()
    reference = run("reference", "reference-db", time.monotonic() + 600)
    deadline = time.monotonic() + 600
    interrupted = run("interrupted", "resumed-db", deadline, pause=True)
    resumed = run("resumed", "resumed-db", deadline)
    assert [s["forward_calls"] for s in (reference, interrupted, resumed)] == [96, 49, 48]
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
    payload_per_cycle = sum(len(v[1]) for v in ref.values()) / 12
    if args.compact:
        catalogs = {}
        for group in ("reference-db", "resumed-db"):
            path = base / group / "payloads.sqlite"
            with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
                if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise ValueError("catalog integrity failed")
                catalogs[group] = {
                    "unique_payloads": db.execute("SELECT COUNT(*) FROM blobs").fetchone()[0],
                    "payload_bytes": db.execute(
                        "SELECT SUM(LENGTH(payload)) FROM blobs"
                    ).fetchone()[0],
                    "catalog_bytes": path.stat().st_size,
                }
        report["compact_storage"] = {
            "catalogs": catalogs,
            "total_output_bytes": size(),
            "long_run_ready": False,
        }
    report.update(
        status="rehearsal_passed",
        **feasibility(cycles, payload_per_cycle),
        payload_bytes_per_cycle=payload_per_cycle,
        checkpoint_hashes={
            p.relative_to(base).as_posix(): file_hash(p) for p in base.rglob("*.sqlite")
        },
    )
except BaseException as error:
    report.update(status="stopped", error=f"{type(error).__name__}: {error}")
    raise
finally:
    report["finished_utc"] = datetime.now(UTC).isoformat()
    save()
    print(report["status"], report.get("error", ""), flush=True)
