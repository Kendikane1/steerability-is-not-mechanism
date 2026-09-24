"""Rehearsal cannot expand earlier scopes; real memory pressure is never induced."""

import io
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import torch
import yaml
from pydantic import ValidationError

from steerability_is_not_mechanism.local_qwen import (
    RehearsalRequest,
    ResumeRequest,
    read_rehearsal_request,
)
from steerability_is_not_mechanism.resource_guard import GIB, SystemReading, check_system
from steerability_is_not_mechanism.sustained import (
    MemorySampler,
    compare_payloads,
    rehearsal_manifest,
)


def test_rehearsal_manifest_identity_and_storage_bound():
    manifest = rehearsal_manifest()
    assert manifest == rehearsal_manifest()
    assert len(manifest) == len({r["id"] for r in manifest}) == 48
    assert all(sum(r["shard"] == i for r in manifest) == 16 for i in range(3))
    assert manifest[24]["fixture"]["intervention"] == "capture"
    assert sum(1 if r["fixture"]["intervention"] == "capture" else 3 for r in manifest) == 96


@pytest.mark.parametrize(
    "field,value",
    [("cycles", 13), ("max_forward_calls", 97), ("scope", "pilot"), ("pressure_policy", "ignore")],
)
def test_rehearsal_budget_cannot_expand(field, value):
    raw = yaml.safe_load(Path("configs/local_rehearsal.yaml").read_text())
    raw[field] = value
    with pytest.raises(ValidationError):
        RehearsalRequest.model_validate(raw)


def test_old_request_stays_separate_and_disabled_fails_early(tmp_path):
    raw = yaml.safe_load(Path("configs/local_rehearsal.yaml").read_text())
    with pytest.raises(ValidationError):
        ResumeRequest.model_validate(raw)
    raw["execution_enabled"] = False
    p = tmp_path / "request.yaml"
    p.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="disabled"):
        read_rehearsal_request(p, tmp_path / "missing")


def test_warning_revision_does_not_accept_critical_or_unknown():
    r = SystemReading(1, 1.1, 2, 0, 11 * GIB, "2", "fixture")
    check_system(r, now=2, baseline_swap=0, startup=True, allow_warning=True)
    for p in (0, 3, 4):
        with pytest.raises(RuntimeError, match="pressure"):
            check_system(
                replace(r, pressure=p), now=2, baseline_swap=0, startup=True, allow_warning=True
            )
    with pytest.raises(RuntimeError, match="pressure"):
        check_system(r, now=2, baseline_swap=0, startup=True)


def payload(value):
    buf = io.BytesIO()
    np.savez(buf, logits=value)
    return buf.getvalue()


def test_full_array_and_margin_checks():
    a = np.ones(64, dtype=np.float32)
    assert compare_payloads(payload(a), payload(a))["logits"]["exact"]
    for b in [np.full(64, np.nan, dtype=np.float32), a.astype(np.float64), a[:32], a + 0.1]:
        with pytest.raises(ValueError):
            compare_payloads(payload(b), payload(a))
    a[:] = 1000
    b = a.copy()
    b[32] += 0.001  # Element-relative gate passes, stricter margin gate must fail.
    with pytest.raises(ValueError, match="margin"):
        compare_payloads(payload(b), payload(a))


def test_sampler_records_then_obeys_stop(monkeypatch, tmp_path):
    monkeypatch.setattr("subprocess.check_output", lambda *a, **k: "1024")
    monitor = MemorySampler(tmp_path, torch.device("cpu"))
    try:
        monitor.check("test")
        assert (tmp_path / "memory.jsonl").exists()
        (tmp_path / "stop").touch()
        with pytest.raises(RuntimeError, match="stop"):
            monitor.check("test")
    finally:
        monitor.close()


def test_sampler_propagates_unavailable_telemetry(monkeypatch, tmp_path):
    monkeypatch.setattr("subprocess.check_output", lambda *a, **k: "unavailable")
    monitor = MemorySampler(tmp_path, torch.device("cpu"))
    monitor.thread.join(2)
    try:
        assert monitor.error and (tmp_path / "monitor_error.json").exists()
        with pytest.raises(RuntimeError, match="RSS"):
            monitor.check("test")
    finally:
        monitor.close()


def test_atomic_publication_recovers_transient_windows_reader(monkeypatch, tmp_path):
    from steerability_is_not_mechanism.sustained import atomic_json

    path = tmp_path / "state.json"
    path.write_text('{"old": true}')
    original = Path.replace
    attempts = []

    def replace(source, target):
        attempts.append(1)
        if len(attempts) == 1:
            assert target.read_text() == '{"old": true}'
            raise PermissionError("reader holds destination")
        return original(source, target)

    monkeypatch.setattr("steerability_is_not_mechanism.sustained.WINDOWS_REPLACE_RETRY", True)
    monkeypatch.setattr(Path, "replace", replace)
    atomic_json(path, {"new": True})
    assert len(attempts) == 2 and '"new": true' in path.read_text()


def test_atomic_publication_persistent_error_stays_bounded(monkeypatch, tmp_path):
    from steerability_is_not_mechanism.sustained import atomic_json

    path = tmp_path / "state.json"
    path.write_text("original")

    def fail(*args):
        raise PermissionError("persistent denial")

    times = iter([0.0, 0.5, 1.1])
    monkeypatch.setattr("steerability_is_not_mechanism.sustained.WINDOWS_REPLACE_RETRY", True)
    monkeypatch.setattr(
        "steerability_is_not_mechanism.sustained.time.monotonic", lambda: next(times)
    )
    monkeypatch.setattr(Path, "replace", fail)
    with pytest.raises(PermissionError):
        atomic_json(path, {"new": True})
    assert path.read_text() == "original"
