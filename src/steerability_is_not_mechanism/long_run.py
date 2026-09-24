"""Fixed synthetic endurance plan; streaming manifests and per-shard audit."""

import hashlib
import json
import math
import sqlite3
from pathlib import Path

import yaml

from .compact_store import CompactShardStore, file_hash
from .engineering_config import load_engineering_config
from .local_qwen import CudaSustainedRequest, _load_verified_adapter
from .resume_jobs import synthetic_jobs
from .shard_store import canonical

CYCLES = 21429
JOBS = CYCLES * 4
SHARDS = math.ceil(JOBS / 16)
MIDPOINT = JOBS // 2
WALL_SECONDS = 21600
MANIFEST_SHA256 = "c00f8116f3f451e5754c3d4c24aeb76535ac5d3faf4147183e96895681bda382"


def jobs():
    fixtures = synthetic_jobs()
    for cycle in range(CYCLES):
        for index, fixture in enumerate(fixtures):
            number = cycle * 4 + index
            yield {
                "id": f"cycle-{cycle:06d}-{fixture.run_id}",
                "index": number,
                "cycle": cycle,
                "shard": number // 16,
                "fixture": fixture.model_dump(),
            }


def manifest(path: Path):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in jobs():
            stream.write(canonical(row) + "\n")
    digest = file_hash(path)
    if digest != MANIFEST_SHA256:
        raise ValueError("fixed manifest hash mismatch")
    return digest


def batches(path: Path):
    batch = []
    with path.open() as stream:
        for expected, line in zip(jobs(), stream, strict=True):
            row = json.loads(line)
            if row != expected:
                raise ValueError("manifest differs from fixed plan")
            batch.append(row)
            if len(batch) == 16:
                yield batch
                batch = []
    if batch:
        yield batch


def request(root: Path):
    value = CudaSustainedRequest.model_validate(
        yaml.safe_load((root / "configs/remote_sustained.yaml").read_text())
    )
    if not value.execution_enabled:
        raise ValueError("sustained execution disabled")
    protocol = root / "configs/local_model_engineering.yaml"
    if file_hash(protocol) != value.protocol_sha256:
        raise ValueError("protocol hash mismatch")
    return value, load_engineering_config(protocol)


def load_adapter(value, spec, root, device):
    if not isinstance(value, CudaSustainedRequest):
        raise ValueError("separate sustained request required")
    return _load_verified_adapter(
        value,
        spec,
        root / "outputs/phase1/p1-005/tokenizer",
        root / "models/Qwen3-0.6B" / spec.model.revision,
        device,
    )


def source_hashes(root):
    paths = sorted((root / "src").rglob("*.py")) + [
        root / p
        for p in (
            "notebooks/run_remote_sustained.py",
            "notebooks/check_remote_sustained.py",
            "configs/remote_sustained.yaml",
            "configs/local_model_engineering.yaml",
            "docs/REMOTE_SUSTAINED_PROTOCOL.md",
            "uv.lock",
        )
    ]
    return {p.relative_to(root).as_posix(): file_hash(p) for p in paths}


def prefix_digest(folder: Path, count: int):
    """Stream original committed row checksums, even while the next INSERT is paused."""
    digest = hashlib.sha256()
    seen = 0
    for shard in range(math.ceil(count / 16)):
        path = folder / f"shard-{shard}.sqlite"
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
            for key, checksum in db.execute("SELECT run_id,sha256 FROM results ORDER BY run_id"):
                if seen >= count:
                    break
                digest.update(canonical([key, checksum]).encode())
                seen += 1
    if seen != count:
        raise ValueError("committed prefix incomplete")
    return digest.hexdigest()


def compare_arms(base, identity, manifest_path, compare, guard=lambda: None):
    count = arrays = 0
    active = {"reference-db": 0.0, "resumed-db": 0.0}
    exact = True
    for batch in batches(manifest_path):
        guard()
        ids = [j["id"] for j in batch]
        records = []
        for group in active:
            store = CompactShardStore(
                base / group / f"shard-{batch[0]['shard']}.sqlite", identity, ids
            )
            try:
                rows = store.completed()
                if set(rows) != set(ids):
                    raise ValueError("incomplete shard")
                active[group] += sum(row[0]["active_seconds"] for row in rows.values())
                records.append(rows)
            finally:
                store.close()
        for key in ids:
            errors = compare(records[0][key][1], records[1][key][1])
            exact = exact and all(r["exact"] for r in errors.values())
            arrays += len(errors)
            count += 1
    if count != JOBS or any(v < 7200 for v in active.values()):
        raise ValueError("incomplete work or insufficient two-hour active duration")
    return {
        "jobs_per_arm": count,
        "arrays_compared": arrays,
        "all_exact": exact,
        "active_seconds": active,
    }
