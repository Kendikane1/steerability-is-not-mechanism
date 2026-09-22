"""Review helpers must fail on missing/altered evidence, not fabricate a pass."""

import hashlib
import runpy
from pathlib import Path

import numpy as np
import pytest

HELPERS = runpy.run_path(str(Path("notebooks/review_phase1.py")))


def test_review_rejects_changed_and_missing_artifacts(tmp_path):
    path = tmp_path / "artifact"
    path.write_bytes(b"original")
    digest = hashlib.sha256(b"original").hexdigest()
    HELPERS["verified_bytes"](path, digest)
    path.write_bytes(b"altered")
    with pytest.raises(ValueError, match="checksum"):
        HELPERS["verified_bytes"](path, digest)
    with pytest.raises(FileNotFoundError):
        HELPERS["verified_bytes"](tmp_path / "missing", digest)


def test_review_rejects_nonfinite_arrays(tmp_path):
    path = tmp_path / "bad.npy"
    np.save(path, np.array([float("nan")]))
    with pytest.raises(ValueError, match="nonfinite"):
        HELPERS["load_array"](path)


def test_console_amendment_does_not_allow_arbitrary_appended_logs(tmp_path):
    path = tmp_path / "interrupted-0.console.log"
    path.write_bytes(b"unrecognized log plus warning")
    original = "b197b5a51c130a86c1baabccbbabc4329d3f9ecf00a21aaacb3ab05d408cc9bf"
    with pytest.raises(ValueError, match="checksum"):
        HELPERS["verify_interrupted_console"](path, original)
    with pytest.raises(ValueError, match="unexpected original"):
        HELPERS["verify_interrupted_console"](path, "changed-report-hash")
