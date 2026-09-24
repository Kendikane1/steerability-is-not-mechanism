"""Offline storage experiment on a completed, independently audited rehearsal."""

import argparse
import hashlib
import json
import math
import sqlite3
from pathlib import Path

from steerability_is_not_mechanism.dedup_archive import export_archive

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--input-dir", type=Path, required=True)
parser.add_argument("--audit", type=Path, required=True)
parser.add_argument("--output-dir", type=Path, required=True)
args = parser.parse_args()
audit = json.loads(args.audit.read_text())
assert audit["status"] == "passed"
for name, digest in audit["files"].items():
    assert hashlib.sha256((args.input_dir / name).read_bytes()).hexdigest() == digest
args.output_dir.mkdir(parents=True, exist_ok=False)
shards = [
    (group, path)
    for group in ("reference-db", "resumed-db")
    for path in sorted((args.input_dir / group).glob("*.sqlite"))
]
archive = args.output_dir / "results.sqlite"
result = export_archive(shards, archive)
with sqlite3.connect(archive) as db:
    max_meta = db.execute("SELECT MAX(LENGTH(CAST(metadata AS BLOB))) FROM jobs").fetchone()[0]
    max_header = db.execute("SELECT MAX(LENGTH(CAST(identity AS BLOB))) FROM headers").fetchone()[0]
cycles = audit["proposed_long_cycles"]
# Prospective design: global immutable manifest once, referenced by hash in each shard header.
# These are engineering estimates, not a frozen live storage format or a worst-case guarantee.
manifest_row_budget = 1024
row_budget = max_meta + 512
header_budget = max_header + 512
jobs = cycles * 4 * 2
shard_count = math.ceil(cycles * 4 / 16) * 2
estimated = (
    result["unique_payload_bytes"]
    + 2 * (jobs * row_budget + shard_count * header_budget + cycles * 4 * manifest_row_budget)
    + 256 * 1024**2
)
result.update(
    archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
    source_audit_sha256=hashlib.sha256(args.audit.read_bytes()).hexdigest(),
    original_checkpoint_bytes=sum(p.stat().st_size for _, p in shards),
    proposed_cycles_per_arm=cycles,
    projected_jobs_both_arms=jobs,
    metadata_budget_bytes_per_job=row_budget,
    header_budget_bytes_per_shard=header_budget,
    global_manifest_budget_bytes_per_job=manifest_row_budget,
    conditional_estimated_long_bytes=estimated,
    conditional_storage_feasible=estimated < 4 * 1024**3,
    assumptions=[
        "Payloads repeat byte-identically; every new distinct payload must still be retained.",
        "Global immutable full manifest stored once; shard headers bind it by hash.",
        "Twice projected metadata/header/manifest bytes plus 256 MiB log/journal reserve.",
        "Live durability, independent shard verification, overhead and hard output cap need validation.",
    ],
)
# Prove the original audit inputs have not been modified by the offline transformation.
for name, digest in audit["files"].items():
    assert hashlib.sha256((args.input_dir / name).read_bytes()).hexdigest() == digest
(args.output_dir / "report.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
