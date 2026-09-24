"""Bounded rehearsal manifest, comparisons and worker memory telemetry."""

import hashlib
import json
import os
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import torch

from .resource_guard import check_mps
from .resume_jobs import synthetic_jobs, unpack

WINDOWS_REPLACE_RETRY = os.name == "nt"


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    # Windows readers may briefly deny replacement while holding the old file open.
    # Retry only metadata publication; persistent errors still fail within one second.
    deadline = time.monotonic() + 1.0
    while True:
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if not WINDOWS_REPLACE_RETRY or time.monotonic() >= deadline:
                raise
            time.sleep(0.01)


def rehearsal_manifest() -> list[dict]:
    return [
        {
            "id": f"cycle-{cycle:04d}-{row.run_id}",
            "cycle": cycle,
            "fixture": row.model_dump(),
            "shard": (cycle * 4 + index) // 16,
        }
        for cycle in range(12)
        for index, row in enumerate(synthetic_jobs())
    ]


def compare_payloads(actual: bytes, reference: bytes) -> dict:
    aa, rr = unpack(actual), unpack(reference)
    if set(aa) != set(rr):
        raise ValueError("result arrays changed")
    errors = {}
    for name, a in aa.items():
        r = rr[name]
        if (
            a.shape != r.shape
            or a.dtype != r.dtype
            or not np.isfinite(a).all()
            or not np.isfinite(r).all()
        ):
            raise ValueError("invalid result shape/dtype/finiteness")
        delta = np.abs(a.astype(np.float64) - r.astype(np.float64))
        if not np.all(delta <= 1e-5 + 1e-5 * np.abs(r.astype(np.float64))):
            raise ValueError("repeated arrays outside tolerance")
        errors[name] = {"exact": bool(np.array_equal(a, r)), "max_abs": float(delta.max())}
    a, r = aa["logits"].astype(np.float64), rr["logits"].astype(np.float64)
    if abs((a[32] - a[33]) - (r[32] - r[33])) > 1e-4:
        raise ValueError("repeated margin outside tolerance")
    return errors


def content_hashes(root: Path) -> dict:
    paths = sorted((root / "src").rglob("*.py")) + [
        root / "notebooks/run_local_rehearsal.py",
        root / "notebooks/check_local_rehearsal.py",
        root / "uv.lock",
        root / "configs/local_model_engineering.yaml",
        root / "configs/local_rehearsal.yaml",
        root / "docs/LOCAL_SUSTAINED_TEST_PLAN.md",
    ]
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


class MemorySampler:
    """One writer owns the sampling log; exceptions stop subsequent forwards."""

    def __init__(self, directory: Path, device: torch.device):
        self.directory, self.device = directory, device
        self.error: str | None = None
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.recommended = torch.mps.recommended_max_memory() if device.type == "mps" else None
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def sample(self, phase: str) -> None:
        with self.lock:
            started = time.monotonic()
            rss = subprocess.check_output(
                ["/bin/ps", "-o", "rss=", "-p", str(os.getpid())],
                text=True,
                timeout=2,
            ).strip()
            if not rss.isdecimal():
                raise RuntimeError("RSS telemetry invalid")
            row = {
                "started": started,
                "finished": time.monotonic(),
                "utc": datetime.now(UTC).isoformat(),
                "phase": phase,
                "rss_bytes": int(rss) * 1024,
                "recommended_bytes": self.recommended,
            }
            if self.device.type == "mps":
                row["driver_bytes"] = torch.mps.driver_allocated_memory()
                row["tensor_bytes"] = torch.mps.current_allocated_memory()
            with (self.directory / "memory.jsonl").open("a") as stream:
                stream.write(json.dumps(row) + "\n")
            atomic_json(self.directory / "memory_latest.json", row)
            if time.monotonic() - started > 5:
                raise RuntimeError("worker memory sample stale")
            if self.device.type == "mps":
                assert self.recommended is not None
                check_mps(row["driver_bytes"], self.recommended)

    def _loop(self):
        try:
            while not self.stop.is_set():
                self.sample("periodic")
                self.stop.wait(1)
        except Exception as error:
            self.error = f"{type(error).__name__}: {error}"
            atomic_json(self.directory / "monitor_error.json", {"error": self.error})

    def check(self, phase: str):
        if self.error:
            raise RuntimeError(self.error)
        if (self.directory / "stop").exists():
            raise RuntimeError("supervisor requested stop")
        self.sample(phase)

    def close(self):
        self.stop.set()
        self.thread.join(5)
        if self.thread.is_alive():
            raise RuntimeError("memory sampler did not stop")
