"""Execute the evidence-only walkthrough in this project's kernel; no model execution."""

import argparse
import json
import sys
from pathlib import Path

import nbformat
from jupyter_client.kernelspec import KernelSpecManager
from jupyter_client.manager import KernelManager
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output-dir", type=Path, required=True)
args = parser.parse_args()
output = args.output_dir.resolve()
output.mkdir(parents=True, exist_ok=False)
kernels = output / "kernels"
spec_dir = kernels / "phase1-review"
spec_dir.mkdir(parents=True)
(spec_dir / "kernel.json").write_text(
    json.dumps(
        {
            "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
            "display_name": "Phase 1 local review",
            "language": "python",
        }
    )
)
manager = KernelManager(
    kernel_name="phase1-review", kernel_spec_manager=KernelSpecManager(kernel_dirs=[str(kernels)])
)
notebook = nbformat.read(ROOT / "notebooks/phase1_engineering_review.ipynb", as_version=4)
client = NotebookClient(
    notebook, km=manager, timeout=120, resources={"metadata": {"path": str(ROOT)}}
)
try:
    client.execute()
    streams = [o["text"] for o in notebook.cells[-1].outputs if o.output_type == "stream"]
    result = json.loads("".join(streams))
    (output / "evidence_review.json").write_text(json.dumps(result, indent=2) + "\n")
    print(result["status"])
finally:
    nbformat.write(notebook, output / "phase1_engineering_review.executed.ipynb")
    if manager.has_kernel:
        manager.shutdown_kernel(now=True)
