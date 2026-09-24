"""Entry for the existing Windows scheduled PythonJob slot; no new task registration."""

import argparse
import json
import msvcrt
import os
import runpy
import sys
import time
from pathlib import Path

from steerability_is_not_mechanism.compact_store import file_hash
from steerability_is_not_mechanism.sustained import atomic_json

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--probe", action="store_true")
args = parser.parse_args()
base = root / "outputs/phase1/p1-027"
expected = json.loads((base / "manual-source-hashes.json").read_text())
for name, digest in expected.items():
    if file_hash(root / name) != digest:
        raise ValueError(f"reviewed file changed: {name}")
with (root / "outputs/phase1/p1-023/manual.lock").open("r+b") as lock:
    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    try:
        if args.probe:
            folder = base / "launcher-probe"
            folder.mkdir(exist_ok=False)
            for i in range(3):
                atomic_json(
                    folder / "report.json", {"status": "running", "pid": os.getpid(), "tick": i}
                )
                time.sleep(5)
            atomic_json(
                folder / "report.json", {"status": "passed", "pid": os.getpid(), "ticks": 3}
            )
        else:
            if json.loads((base / "launcher-probe/report.json").read_text())["status"] != "passed":
                raise ValueError("scheduled launcher probe not passed")
            os.environ.update(
                HF_HUB_OFFLINE="1",
                TRANSFORMERS_OFFLINE="1",
                HF_DEACTIVATE_ASYNC_LOAD="1",
                CUBLAS_WORKSPACE_CONFIG=":4096:8",
            )
            sys.argv = [
                str(root / "notebooks/check_remote_sustained.py"),
                "--output-dir",
                str(base / "manual-sustained-01"),
            ]
            runpy.run_path(sys.argv[0], run_name="__main__")
    finally:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
