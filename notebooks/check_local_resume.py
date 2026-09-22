"""P1-016 supervised hard-kill/restart test; only the fixed local synthetic shard runner."""

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import yaml

from steerability_is_not_mechanism.process_logs import ProcessLog
from steerability_is_not_mechanism.resume_jobs import jobs_for_shard, synthetic_jobs, unpack
from steerability_is_not_mechanism.shard_store import result_hash

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output-dir", type=Path, required=True)
args = parser.parse_args()
base = args.output_dir.resolve()
base.mkdir(parents=True, exist_ok=False)
report = {"started_at_utc": datetime.now(UTC).isoformat(), "status": "running", "attempts": []}
report_path = base / "report.json"
env = os.environ.copy()
env.update(
    HF_HUB_OFFLINE="1",
    TRANSFORMERS_OFFLINE="1",
    PYTORCH_ENABLE_MPS_FALLBACK="0",
    HF_DEACTIVATE_ASYNC_LOAD="1",
)


def save():
    report_path.write_text(json.dumps(report, indent=2) + "\n")


def snapshot(path):
    db = sqlite3.connect(f"file:{path}?mode=rw", uri=True)
    try:
        assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        rows = db.execute(
            "SELECT run_id,metadata,payload,sha256 FROM results ORDER BY run_id"
        ).fetchall()
        for _, meta, blob, digest in rows:
            assert result_hash(meta, blob) == digest
        return {row[0]: (json.loads(row[1]), row[2], row[3]) for row in rows}
    finally:
        db.close()


def run(label, destination, shard, kill_job=None, request=None, expected=0):
    attempt = base / label
    command = [
        sys.executable,
        str(ROOT / "notebooks/run_local_resume.py"),
        "--run-dir",
        str(base / destination),
        "--attempt-dir",
        str(attempt),
        "--shard",
        str(shard),
    ]
    if kill_job:
        command += ["--pause-before-commit", kill_job]
    if request:
        command += ["--request", str(request)]
    item = {"label": label, "command": command, "expected_exit_code": expected}
    report["attempts"].append(item)
    save()
    proc = subprocess.Popen(
        command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    assert proc.stdout is not None
    capture = ProcessLog(proc.stdout, base / f"{label}.console.log")
    try:
        deadline = time.monotonic() + 180
        while proc.poll() is None:
            if kill_job and (attempt / "ready.json").exists():
                ready = json.loads((attempt / "ready.json").read_text())
                assert ready == {"pid": proc.pid, "job": kill_job}
                db_path = base / destination / f"shard-{shard}.sqlite"
                journal = Path(str(db_path) + "-journal")
                assert journal.exists() and journal.stat().st_size > 0
                item["rollback_journal_bytes_before_kill"] = journal.stat().st_size
                item["committed_before_kill"] = {k: v[2] for k, v in snapshot(db_path).items()}
                assert set(item["committed_before_kill"]) == {jobs_for_shard(0)[0].run_id}
                proc.kill()  # Actual SIGKILL on this owned local worker, not a graceful return.
                item["kill_signal"] = "SIGKILL"
                break
            if time.monotonic() > deadline:
                raise TimeoutError(f"{label} exceeded 180 seconds")
            time.sleep(0.1)
        code = proc.wait(timeout=15)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=15)
        capture.finish()  # Wait for inherited writers too, before hashing.
    item["exit_code"] = code
    state = json.loads((attempt / "attempt.json").read_text())
    item["model_loaded"] = state["model_loaded"]
    item["forward_calls"] = state["forward_calls"]
    item["executed"] = state["executed"]
    item["skipped"] = state["skipped"]
    item["attempt_sha256"] = hashlib.sha256((attempt / "attempt.json").read_bytes()).hexdigest()
    item["console_sha256"] = hashlib.sha256(
        (base / f"{label}.console.log").read_bytes()
    ).hexdigest()
    save()
    assert code == expected, (label, code, state.get("error"))
    print(label, code, "forwards", state["forward_calls"], flush=True)
    return state


save()
try:
    run("reference-0", "reference", 0)
    run("reference-1", "reference", 1)
    kill_job = jobs_for_shard(0)[1].run_id
    interrupted = run("interrupted-0", "resumed", 0, kill_job=kill_job, expected=-9)
    before = snapshot(base / "resumed/shard-0.sqlite")
    assert set(before) == {jobs_for_shard(0)[0].run_id}
    resumed = run("resumed-0", "resumed", 0)
    assert resumed["skipped"] == list(before)
    after = snapshot(base / "resumed/shard-0.sqlite")
    assert all(after[k][2] == v[2] for k, v in before.items())
    assert set(resumed["executed"]) == {r.run_id for r in jobs_for_shard(0)} - set(before)
    run("resumed-1", "resumed", 1)
    replay = run("completed-replay", "resumed", 0)
    assert replay["forward_calls"] == 0 and not replay["model_loaded"] and not replay["executed"]
    assert replay["completed_at_start"] == replay["completed_at_end"]
    modified = yaml.safe_load((ROOT / "configs/local_resume.yaml").read_text())
    modified["device"] = "cpu"  # Recorded request identity changes even on a CPU-only machine.
    if replay["identity"]["request"]["device"] == "cpu":
        modified["device"] = "auto"
    bad = base / "incompatible-request.yaml"
    bad.write_text(yaml.safe_dump(modified))
    refused = run("incompatible", "resumed", 0, request=bad, expected=1)
    assert refused["forward_calls"] == 0 and not refused["model_loaded"]
    assert "incompatible resume identity" in refused["error"]
    comparisons = []
    seen = set()
    for shard in (0, 1):
        reference = snapshot(base / "reference" / f"shard-{shard}.sqlite")
        actual = snapshot(base / "resumed" / f"shard-{shard}.sqlite")
        assert set(reference) == set(actual) == {r.run_id for r in jobs_for_shard(shard)}
        assert not seen.intersection(actual)
        seen.update(actual)
        for key in reference:
            rm, rb, _ = reference[key]
            am, ab, _ = actual[key]
            assert rm["row"] == am["row"] and rm["input_ids"] == am["input_ids"]
            ra, aa = unpack(rb), unpack(ab)
            assert set(ra) == set(aa)
            audit = {}
            for name in ra:
                x, y = aa[name], ra[name]
                assert (
                    x.shape == y.shape
                    and x.dtype == y.dtype
                    and np.isfinite(x).all()
                    and np.isfinite(y).all()
                )
                error = np.abs(x.astype(np.float64) - y.astype(np.float64))
                assert np.all(error <= 1e-5 + 1e-5 * np.abs(y.astype(np.float64)))
                audit[name] = {
                    "exact_equal": np.array_equal(x, y),
                    "max_abs_error": float(error.max()),
                }
            margin_error = abs(am["margin"] - rm["margin"])
            assert margin_error <= 1e-4
            for meta, arrays in ((am, aa), (rm, ra)):
                assert (
                    abs(float(arrays["logits"][32]) - float(arrays["logits"][33]) - meta["margin"])
                    <= 1e-12
                )
                assert meta["hooks_clear"]
                if "geometry" in meta:
                    assert meta["geometry"]["passed"] and meta["unedited_positions_exact"]
            comparisons.append({"run_id": key, "arrays": audit, "margin_abs_error": margin_error})
    assert seen == {r.run_id for r in synthetic_jobs()}
    report["comparisons"] = comparisons
    report["checkpoint_hashes"] = {
        str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(base.rglob("*.sqlite"))
    }
    report["status"] = "passed"
except BaseException as error:
    report["status"] = "failed"
    report["error"] = f"{type(error).__name__}: {error}"
    raise
finally:
    report["finished_at_utc"] = datetime.now(UTC).isoformat()
    save()
    print("Report:", report_path, flush=True)
