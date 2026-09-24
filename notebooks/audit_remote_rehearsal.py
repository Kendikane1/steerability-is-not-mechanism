import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from steerability_is_not_mechanism.compact_store import snapshot as compact_snapshot
from steerability_is_not_mechanism.coordinate_check import geometry_report
from steerability_is_not_mechanism.engineering_config import load_engineering_config
from steerability_is_not_mechanism.remote_cuda import check_resources
from steerability_is_not_mechanism.remote_rehearsal import feasibility
from steerability_is_not_mechanism.resume_jobs import unpack
from steerability_is_not_mechanism.shard_store import result_hash
from steerability_is_not_mechanism.sustained import compare_payloads, rehearsal_manifest

parser = argparse.ArgumentParser(description="Offline audit of the fixed synthetic CUDA rehearsal")
parser.add_argument("--input-dir", type=Path, required=True)
parser.add_argument("--source-root", type=Path, required=True)
parser.add_argument("--output-dir", type=Path, required=True)
args = parser.parse_args()
base = args.output_dir
base.mkdir(parents=True, exist_ok=False)
d = args.input_dir
r = json.loads((d / "report.json").read_text())
assert r["status"] == "rehearsal_passed"
for name, h in r["source_hashes"].items():
    assert hashlib.sha256((args.source_root / name).read_bytes()).hexdigest() == h, name
assert r["manifest"] == rehearsal_manifest()
samples = []
calls = []
for a in r["attempts"]:
    assert (
        hashlib.sha256((d / (a["label"] + ".console.log")).read_bytes()).hexdigest()
        == a["console_sha256"]
    )
    state = json.loads((d / a["label"] / "attempt.json").read_text())
    assert state == a["state"]
    calls.append(state["forward_calls"])
    p = d / a["label"] / "resources.jsonl"
    if p.exists():
        samples.extend(json.loads(x) for x in p.read_text().splitlines())
assert calls == [96, 49, 48, 0, 0]
assert [a["label"] for a in r["attempts"]] == [
    "reference",
    "interrupted",
    "resumed",
    "replay",
    "incompatible",
]
for a in r["attempts"][-2:]:
    assert not a["state"]["model_loaded"]
assert "incompatible resume identity" in r["attempts"][-1]["state"]["error"]
for sample in samples:
    check_resources(sample, startup=False)
for rel, h in r["checkpoint_hashes"].items():
    assert hashlib.sha256((d / rel).read_bytes()).hexdigest() == h
spec = load_engineering_config(args.source_root / "configs/local_model_engineering.yaml")
groups = {}
for group in ["reference-db", "resumed-db"]:
    rows = {}
    fixtures = {}
    if r.get("storage") == "compact-v1":
        label = "reference" if group == "reference-db" else "interrupted"
        identity = json.loads((d / label / "attempt.json").read_text())["identity"]
        records = [
            (k, json.dumps(m), p, h)
            for k, (m, p, h) in compact_snapshot(d / group, identity).items()
        ]
    else:
        records = []
        for p in sorted((d / group).glob("*.sqlite")):
            with sqlite3.connect(p.resolve().as_uri() + "?mode=ro", uri=True) as db:
                assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
                records.extend(db.execute("SELECT * FROM results ORDER BY run_id"))
    for key, meta, payload, h in records:
        assert key not in rows
        if r.get("storage") != "compact-v1":
            assert result_hash(meta, payload) == h
        m = json.loads(meta)
        rows[key] = (m, payload, h)
        original = fixtures.setdefault(m["fixture_id"], payload)
        compare_payloads(payload, original)
        arrays = unpack(payload)
        if "geometry" in m:
            g = geometry_report(
                arrays["activation"],
                arrays["applied"],
                arrays["donor"],
                arrays["direction"],
                spec.checks,
            )
            assert g["passed"] and m["geometry"]["passed"]
    assert set(rows) == {x["id"] for x in rehearsal_manifest()}
    groups[group] = rows
comparisons = {
    k: compare_payloads(groups["resumed-db"][k][1], v[1]) for k, v in groups["reference-db"].items()
}
assert comparisons == r["comparisons"]
prior = r["attempts"][1]["committed_before_kill"]
assert len(prior) == 24
assert all(groups["resumed-db"][k][2] == h for k, h in prior.items())
cycles = [
    sum(v[0]["active_seconds"] for v in groups["reference-db"].values() if v[0]["cycle"] == i)
    for i in range(12)
]
size = sum(len(v[1]) for v in groups["reference-db"].values()) / 12
assert all(r[k] == v for k, v in feasibility(cycles, size).items())
files = {
    p.relative_to(d).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in d.rglob("*")
    if p.is_file()
}
summary = {
    "status": "passed",
    "calls": calls,
    "jobs_per_arm": 48,
    "array_comparisons": sum(len(c) for c in comparisons.values()),
    "all_exact": all(x["exact"] for c in comparisons.values() for x in c.values()),
    "min_gpu_free": min(x["gpu_free"] for x in samples),
    "peak_allocated": max(x["peak_allocated"] for x in samples),
    "min_ram_free": min(x["ram"]["avail_phys"] for x in samples),
    "min_disk_free": min(x["disk_free"] for x in samples),
    "samples": len(samples),
    "payload_bytes_per_cycle": size,
    **feasibility(cycles, size),
    "report_sha256": hashlib.sha256((d / "report.json").read_bytes()).hexdigest(),
    "files": files,
}
(base / "audit.json").write_text(json.dumps(summary, indent=2))
print(json.dumps({k: v for k, v in summary.items() if k != "files"}, indent=2), flush=True)
