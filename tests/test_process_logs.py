"""Late descendant output must be captured before checksumming the log."""

import subprocess
import sys

import pytest

from steerability_is_not_mechanism.process_logs import ProcessLog


def test_log_includes_output_after_primary_worker_exits(tmp_path):
    child = "import time; time.sleep(0.2); print('late cleanup', flush=True)"
    parent = (
        "import subprocess,sys; print('worker',flush=True); "
        f"subprocess.Popen([sys.executable, '-c', {child!r}])"
    )
    proc = subprocess.Popen([sys.executable, "-c", parent], stdout=subprocess.PIPE)
    assert proc.stdout is not None
    path = tmp_path / "console.log"
    capture = ProcessLog(proc.stdout, path)
    assert proc.wait(timeout=5) == 0
    capture.finish(timeout=5)
    assert path.read_text() == "worker\nlate cleanup\n"


def test_unfinished_output_is_not_certified(tmp_path):
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"], stdout=subprocess.PIPE
    )
    assert proc.stdout is not None
    capture = ProcessLog(proc.stdout, tmp_path / "console.log")
    try:
        with pytest.raises(TimeoutError, match="do not hash"):
            capture.finish(timeout=0.01)
    finally:
        proc.kill()
        proc.wait(timeout=5)
        capture.finish(timeout=5)
