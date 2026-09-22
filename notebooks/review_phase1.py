"""Read-only audit of pinned historical Phase 1 evidence. No model construction or network."""

import hashlib
import io
import json
import sqlite3
from pathlib import Path

import numpy as np
import yaml

from steerability_is_not_mechanism.qwen_preflight import TOKENIZER_FILES, verify_file_bundle

RECORDS = {
    "tokenizer": (
        "p1-005/inspection.json",
        "dc0a430e3d47c41e5bd2d03f4ae3eeecd2a4564c416c900d863dc1a4e1320aa2",
    ),
    "scoring": (
        "p1-013/mps-04/run.json",
        "84adc99b5c0cacc2e3b5a4184366468fe826ea171c45fe6837588bbb18bd47ba",
    ),
    "noop": (
        "p1-014/mps-01/run.json",
        "1c52780ada75e2c82f0a056ed44641073e537f676f92a6f8e7500b03a0d92305",
    ),
    "coordinate": (
        "p1-015/mps-01/run.json",
        "5febc9a606bb03eccc9668a55fc8d38f9b7d0144ed7a1b5f43a6e67d6014610a",
    ),
    "resume": (
        "p1-016/check-01/report.json",
        "f2f453b5b3027b0a308fd8c957a5b11355b6f131c22a48e8335d7d315bd6bc68",
    ),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verified_bytes(path: Path, digest: str) -> None:
    with path.open("rb") as handle:
        actual = hashlib.file_digest(handle, "sha256").hexdigest()
    require(actual == digest, f"artifact checksum mismatch: {path.name}")


def verify_interrupted_console(path: Path, original_digest: str) -> dict:
    """Exact P1-016 provenance amendment; never accept an arbitrary appended log."""
    expected_original = "b197b5a51c130a86c1baabccbbabc4329d3f9ecf00a21aaacb3ab05d408cc9bf"
    current_digest = "3b7127368810d8f9a3ca0f66e597e51084adaadbe68e968695a192dd08e2a1b8"
    require(original_digest == expected_original, "unexpected original console hash")
    verified_bytes(path, current_digest)
    data = path.read_bytes()
    require(
        len(data) == 5021 and hashlib.sha256(data[:4735]).hexdigest() == original_digest,
        "original console prefix mismatch",
    )
    return {
        "artifact": "p1-016/check-01/interrupted-0.console.log",
        "original_prefix_bytes": 4735,
        "original_prefix_sha256": original_digest,
        "current_sha256": current_digest,
        "appended_bytes": 286,
        "appended_text": data[4735:].decode(),
        "interpretation": "Delayed resource_tracker shutdown warning after worker SIGKILL; "
        "historical report and log preserved unchanged. Full log hash was not final at capture.",
    }


def load_array(path: Path) -> np.ndarray:
    value = np.load(path, allow_pickle=False)
    require(np.isfinite(value).all(), f"nonfinite array: {path.name}")
    return value


def review(root: Path) -> dict:
    base = root / "outputs/phase1"
    records = {}
    for key, (relative, digest) in RECORDS.items():
        verified_bytes(base / relative, digest)
        records[key] = json.loads((base / relative).read_text())
    verify_file_bundle(base / "p1-005/tokenizer", TOKENIZER_FILES)
    revision = records["tokenizer"]["repository_revision"]
    verified_bytes(
        root / "models/Qwen3-0.6B" / revision / "model.safetensors",
        "f47f71177f32bcd101b7573ec9171e6a57f4f4d31148d38e382306f42996874b",
    )
    scoring = records["scoring"]
    require(scoring["input_ids"][0] == records["tokenizer"]["input_ids"], "token IDs changed")
    verified_bytes(base / "p1-013/mps-04/final_token_logits.npy", scoring["logits_sha256"])
    logits = load_array(base / "p1-013/mps-04/final_token_logits.npy").astype(np.float64)
    require(logits.shape == (151936,), "unexpected scoring shape")
    margin = float(logits[32] - logits[33])
    probabilities = np.exp(logits - np.max(logits))
    probabilities /= probabilities.sum()
    require(abs(margin - scoring["scores"]["margin"]) <= 1e-12, "score discrepancy")
    require(abs(probabilities[32] - scoring["scores"]["p_A"]) <= 1e-12, "probability discrepancy")
    for key in ("noop", "coordinate"):
        directory = (base / RECORDS[key][0]).parent
        for name, digest in records[key]["artifacts"].items():
            verified_bytes(directory / name, digest)
            load_array(directory / name)
    noop_dir = base / "p1-014/mps-01"
    reference = load_array(noop_dir / "baseline_1_logits.npy")
    for name in ("baseline_2", "baseline_3", "capture", "identity", "post_hook"):
        require(
            np.array_equal(reference, load_array(noop_dir / f"{name}_logits.npy")),
            "no-op scores changed",
        )
    require(
        np.array_equal(
            load_array(noop_dir / "capture_activation.npy"),
            load_array(noop_dir / "identity_activation.npy"),
        ),
        "identity captures changed",
    )
    coordinate = records["coordinate"]
    directory = base / "p1-015/mps-01"
    geometry = []
    for row in coordinate["comparisons"]:
        name, context = row["name"], row["context"]
        actual = load_array(directory / f"{name}_logits.npy")
        if "_paired_" not in name:
            require(
                np.array_equal(actual, load_array(directory / f"{context}_baseline_1_logits.npy")),
                "zero/repeat change",
            )
        require(
            abs(float(actual[32]) - float(actual[33]) - row["margin"]) <= 1e-12,
            "coordinate score mismatch",
        )
        require(row["hooks_clear"], "hook cleanup evidence missing")
        if "geometry" in row:
            v = load_array(directory / f"direction_{name.split('_')[0]}.npy")
            h = load_array(directory / f"{context}_capture_activation.npy").astype(np.float64)
            edited = load_array(directory / f"{name}_applied.npy").astype(np.float64)
            donor_context = (
                ("low" if context == "high" else "high") if "_paired_" in name else context
            )
            donor = load_array(directory / f"{donor_context}_capture_activation.npy").astype(
                np.float64
            )
            target = float(v @ donor)
            delta = edited - h
            projection_error = abs(float(v @ edited) - target)
            orthogonal_error = float(np.linalg.norm(delta - (v @ delta) * v))
            limit = 1e-5 * max(1.0, np.linalg.norm(h), np.linalg.norm(edited), abs(target))
            require(projection_error <= limit and orthogonal_error <= limit, "geometry failed")
            require(
                row["unedited_positions_exact"] and row["applied_matches_requested"],
                "position/write audit missing",
            )
            geometry.append(
                {
                    "name": name,
                    "projection_error": projection_error,
                    "orthogonal_error": orthogonal_error,
                }
            )
    resume = records["resume"]
    directory = base / "p1-016/check-01"
    require(resume["status"] == "passed", "resume did not pass")
    for name, digest in resume["checkpoint_hashes"].items():
        verified_bytes(directory / name, digest)
    arrays_by_run = {"reference": {}, "resumed": {}}
    for group in arrays_by_run:
        for shard in (0, 1):
            path = directory / group / f"shard-{shard}.sqlite"
            db = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
            try:
                rows = db.execute("SELECT run_id,metadata,payload,sha256 FROM results").fetchall()
                for run_id, metadata, payload, digest in rows:
                    require(
                        hashlib.sha256(metadata.encode() + b"\x00" + payload).hexdigest() == digest,
                        "row checksum failed",
                    )
                    require(run_id not in arrays_by_run[group], "duplicate committed ID")
                    with np.load(io.BytesIO(payload), allow_pickle=False) as data:
                        arrays_by_run[group][run_id] = {k: data[k] for k in data.files}
            finally:
                db.close()
    require(
        set(arrays_by_run["reference"]) == set(arrays_by_run["resumed"])
        and len(arrays_by_run["reference"]) == 4,
        "job IDs missing",
    )
    count = 0
    for run_id, arrays in arrays_by_run["reference"].items():
        other = arrays_by_run["resumed"][run_id]
        require(set(arrays) == set(other), "array names changed")
        for name, value in arrays.items():
            require(
                np.isfinite(value).all() and np.array_equal(value, other[name]),
                "resume arrays differ",
            )
            count += 1
    attempts = {x["label"]: x for x in resume["attempts"]}
    require(attempts["interrupted-0"]["exit_code"] == -9, "no hard interruption")
    require(
        attempts["completed-replay"]["forward_calls"] == 0
        and not attempts["completed-replay"]["model_loaded"],
        "replay did model work",
    )
    require(
        attempts["incompatible"]["exit_code"] == 1
        and attempts["incompatible"]["forward_calls"] == 0
        and not attempts["incompatible"]["model_loaded"],
        "incompatible resume not refused",
    )
    amendments = []
    for label, attempt in attempts.items():
        verified_bytes(directory / label / "attempt.json", attempt["attempt_sha256"])
        console = directory / f"{label}.console.log"
        if label == "interrupted-0":
            amendments.append(verify_interrupted_console(console, attempt["console_sha256"]))
        else:
            verified_bytes(console, attempt["console_sha256"])
    for name in ("pilot.yaml", "locked_experiment.yaml"):
        config = yaml.safe_load((root / "configs" / name).read_text())
        require(
            config["execution_enabled"] is False and config["model"]["allow_download"] is False,
            "scientific guard enabled",
        )
    old = json.loads((directory / "reference-0/attempt.json").read_text())["identity"][
        "source_hashes"
    ]
    changed = []
    for name, digest in old.items():
        with (root / name).open("rb") as handle:
            if hashlib.file_digest(handle, "sha256").hexdigest() != digest:
                changed.append(name)
    require(
        set(changed) <= {"src/steerability_is_not_mechanism/shard_store.py"},
        "unreviewed runtime source changes",
    )
    added = sorted(
        str(path.relative_to(root))
        for path in (root / "src").rglob("*.py")
        if str(path.relative_to(root)) not in old
    )
    require(
        set(added) <= {"src/steerability_is_not_mechanism/process_logs.py"},
        "unreviewed runtime source additions",
    )
    return {
        "status": "saved_evidence_verified_with_documented_console_amendment",
        "provenance_amendments": amendments,
        "model_forward_calls": 0,
        "revision": revision,
        "records": RECORDS,
        "p_A": float(probabilities[32]),
        "p_B": float(probabilities[33]),
        "margin": margin,
        "geometry": geometry,
        "resumed_jobs": 4,
        "resumed_arrays_exact": count,
        "runtime_files_changed_since_P1_016": changed,
        "runtime_files_added_since_P1_016": added,
        "bounded_local_evidence": "passed",
        "multi_hour_and_peak_headroom": "not established",
        "scientific_readiness": "not met",
    }
