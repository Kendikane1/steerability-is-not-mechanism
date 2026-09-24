"""Manual fixed overnight engineering supervisor. Never retries an unexpected failure."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from steerability_is_not_mechanism.compact_store import file_hash
from steerability_is_not_mechanism.long_run import (
    JOBS,
    MIDPOINT,
    WALL_SECONDS,
    compare_arms,
    manifest,
    prefix_digest,
    source_hashes,
)
from steerability_is_not_mechanism.process_control import kill_owned_tree, validate_worker_pid
from steerability_is_not_mechanism.process_logs import ProcessLog
from steerability_is_not_mechanism.remote_cuda import GIB, windows_memory
from steerability_is_not_mechanism.remote_rehearsal import check_liveness
from steerability_is_not_mechanism.sustained import atomic_json, compare_payloads

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output-dir", type=Path, required=True)
args = parser.parse_args()
base = args.output_dir.resolve()
base.mkdir(parents=True, exist_ok=False)
manifest_path = base / "manifest.jsonl"
report = {
    "status": "starting",
    "utc": datetime.now(UTC).isoformat(),
    "source_hashes": source_hashes(ROOT),
    "manifest_sha256": manifest(manifest_path),
    "attempts": [],
    "wall_seconds_per_arm": WALL_SECONDS,
}


def save():
    atomic_json(base / "report.json", report)


def guard():
    if (base / "STOP").exists():
        raise RuntimeError("manual stop requested")
    ram = windows_memory()
    total = 0
    for p in base.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except FileNotFoundError:
            pass
    if shutil.disk_usage(base).free < 20 * GIB or total >= 4 * GIB:
        raise RuntimeError("disk/output limit exceeded")
    if ram["avail_phys"] < GIB // 2 or ram["avail_commit"] < GIB // 2 or ram["load"] >= 95:
        raise RuntimeError("RAM/commit reserve breached")
    return ram, total


def run(label, group, deadline, pause=False, incompatible=False, expected=0):
    attempt = base / label
    command = [
        sys.executable,
        str(ROOT / "notebooks/run_remote_sustained.py"),
        "--run-dir",
        str(base / group),
        "--attempt-dir",
        str(attempt),
        "--manifest",
        str(manifest_path),
    ]
    if pause:
        command.append("--pause-midpoint")
    if incompatible:
        command.append("--incompatible")
    item = {"label": label, "command": command}
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
            ram, total = guard()
            with (base / "system.jsonl").open("a") as stream:
                stream.write(
                    json.dumps({"attempt": label, "time": now, "ram": ram, "output_bytes": total})
                    + "\n"
                )
            if now > deadline:
                raise TimeoutError("arm deadline exceeded")
            state_path = attempt / "attempt.json"
            latest_path = attempt / "resources_latest.json"
            state = json.loads(state_path.read_text()) if state_path.exists() else None
            latest = json.loads(latest_path.read_text()) if latest_path.exists() else None
            if (attempt / "abort.json").exists():
                raise RuntimeError((attempt / "abort.json").read_text())
            check_liveness(state, latest, now, start)
            if pause and (attempt / "ready.json").exists():
                ready = json.loads((attempt / "ready.json").read_text())
                assert ready["shard"] == MIDPOINT // 16
                validate_worker_pid(proc.pid, ready["pid"])
                assert (base / group / f"shard-{ready['shard']}.sqlite-journal").stat().st_size > 0
                item["prefix_sha256"] = prefix_digest(base / group, MIDPOINT)
                if time.monotonic() - now > 300 or time.monotonic() > deadline:
                    raise TimeoutError("fault inspection exceeded deadline")
                guard()
                latest = json.loads(latest_path.read_text())
                if proc.poll() is not None or (attempt / "abort.json").exists():
                    raise RuntimeError("worker failed before intentional termination")
                if time.monotonic() - latest["time"] > 5:
                    raise RuntimeError("telemetry stale at intentional termination")
                kill_owned_tree(proc)
                item["intentional_termination"] = True
                break
            time.sleep(1)
        code = proc.wait(timeout=10)
        state = json.loads((attempt / "attempt.json").read_text())
        item.update(exit_code=code, state=state)
        if (pause and not (item.get("intentional_termination") and code != 0)) or (
            not pause and code != expected
        ):
            raise RuntimeError(f"worker exit {code}: {state.get('error')}")
        return state
    finally:
        if proc.poll() is None:
            kill_owned_tree(proc)
        item["exit_code"] = proc.returncode
        if (attempt / "attempt.json").exists():
            item["state"] = json.loads((attempt / "attempt.json").read_text())
        capture.finish()
        item["console_sha256"] = file_hash(base / f"{label}.console.log")
        save()


save()
try:
    ram, _ = guard()
    if ram["avail_phys"] < GIB or ram["avail_commit"] < GIB:
        raise RuntimeError("startup RAM reserve breached")
    reference = run("reference", "reference-db", time.monotonic() + WALL_SECONDS)
    deadline = time.monotonic() + WALL_SECONDS
    interrupted = run("interrupted", "resumed-db", deadline, pause=True)
    resumed = run("resumed", "resumed-db", deadline)
    assert [x["forward_calls"] for x in (reference, interrupted, resumed)] == [171432, 85717, 85716]
    assert (
        reference["executed"] == JOBS
        and resumed["skipped"] == MIDPOINT
        and resumed["executed"] == JOBS - MIDPOINT
    )
    assert prefix_digest(base / "resumed-db", MIDPOINT) == report["attempts"][1]["prefix_sha256"]
    replay = run("replay", "resumed-db", time.monotonic() + 3600)
    bad = run("incompatible", "resumed-db", time.monotonic() + 180, incompatible=True, expected=1)
    assert replay["skipped"] == JOBS and replay["forward_calls"] == 0 and not replay["model_loaded"]
    assert (
        bad["forward_calls"] == 0
        and not bad["model_loaded"]
        and "incompatible resume identity" in bad["error"]
    )
    audit_deadline = time.monotonic() + 3600

    def audit_guard():
        guard()
        if time.monotonic() > audit_deadline:
            raise TimeoutError("final audit exceeded one hour")

    report["comparison"] = compare_arms(
        base, reference["identity"], manifest_path, compare_payloads, audit_guard
    )
    report["memory_growth"] = {
        label: json.loads((base / label / "memory-growth.json").read_text())
        for label in ("reference", "interrupted", "resumed")
    }
    for metrics in report["memory_growth"].values():
        assert all(r["passed"] for r in metrics.values())
    with (base / "checkpoint-hashes.jsonl").open("x") as stream:
        for path in sorted(base.rglob("*.sqlite")):
            audit_guard()
            stream.write(
                json.dumps({"path": path.relative_to(base).as_posix(), "sha256": file_hash(path)})
                + "\n"
            )
    report.update(
        status="sustained_passed",
        checkpoint_index_sha256=file_hash(base / "checkpoint-hashes.jsonl"),
    )
except BaseException as error:
    report.update(status="stopped", error=f"{type(error).__name__}: {error}")
    raise
finally:
    report["finished_utc"] = datetime.now(UTC).isoformat()
    save()
    print(
        json.dumps(
            {
                "status": report["status"],
                "error": report.get("error"),
                "report": str(base / "report.json"),
            }
        ),
        flush=True,
    )
