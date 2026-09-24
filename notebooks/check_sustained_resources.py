"""Read-only startup gate for P1-019. Never imports torch or loads a model."""

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from steerability_is_not_mechanism.resource_guard import check_system, read_system

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output-dir", type=Path, required=True)
args = parser.parse_args()
args.output_dir.mkdir(parents=True, exist_ok=False)
record = {
    "utc": datetime.now(UTC).isoformat(),
    "status": "starting",
    "model_loaded": False,
    "forward_calls": 0,
    "source_hashes": {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [
            Path(__file__).resolve(),
            ROOT / "src/steerability_is_not_mechanism/resource_guard.py",
        ]
    },
}
try:
    reading = read_system(ROOT)
    record["reading"] = reading.as_dict()
    check_system(reading, now=time.monotonic(), baseline_swap=reading.swap_bytes, startup=True)
    record["status"] = "startup_system_gate_passed_not_model_headroom"
except Exception as error:
    record["status"] = "refused"
    record["error"] = f"{type(error).__name__}: {error}"
finally:
    (args.output_dir / "report.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
raise SystemExit(0 if record["status"].startswith("startup_system_gate_passed") else 1)
