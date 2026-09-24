"""Fixed plan and bounded memory gate tests; no model loading."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from steerability_is_not_mechanism.long_memory import GrowthWindow
from steerability_is_not_mechanism.long_run import (
    CYCLES,
    JOBS,
    MIDPOINT,
    batches,
    jobs,
    manifest,
    request,
)


def test_fixed_manifest_roundtrip_and_midpoint(tmp_path):
    path = tmp_path / "manifest.jsonl"
    digest = manifest(path)
    count = 0
    for batch in batches(path):
        assert 1 <= len(batch) <= 16
        count += len(batch)
    assert count == JOBS == 85716 and CYCLES == 21429 and len(digest) == 64
    before = 0
    for row in jobs():
        calls = 1 if row["fixture"]["intervention"] == "capture" else 3
        if row["index"] == MIDPOINT:
            assert calls == 1 and before == 85716
            break
        before += calls
    with pytest.raises(FileExistsError):
        manifest(path)


def test_changed_manifest_refused(tmp_path):
    p = tmp_path / "bad"
    p.write_text(json.dumps({"id": "wrong"}) + "\n")
    with pytest.raises(ValueError):
        list(batches(p))


def test_fixed_request_budget():
    value, _ = request(Path(__file__).resolve().parents[1])
    assert value.max_forward_calls == 171432
    with pytest.raises(ValidationError):
        type(value).model_validate(value.model_dump() | {"max_forward_calls": 171433})


def test_memory_windows_are_bounded_and_detect_growth():
    window = GrowthWindow()
    for second in range(2400):
        window.add(second, 1024**3, 1024**3)
        window.add(second + 0.1, 1024**3, 1024**3)
    assert len(window.baseline) == 600 and len(window.tail) == 600
    assert all(v["passed"] for v in window.result().values())
    for second in range(2400, 3100):
        window.add(second, 2 * 1024**3, 1024**3)
    with pytest.raises(ValueError, match="growth"):
        window.result()


def test_insufficient_memory_history_refused():
    with pytest.raises(ValueError, match="insufficient"):
        GrowthWindow().result()


def test_streamed_comparison_preserves_rows_and_requires_duration(tmp_path, monkeypatch):
    import steerability_is_not_mechanism.long_run as module
    from steerability_is_not_mechanism.compact_store import CompactShardStore

    batch = [{"id": "a", "shard": 0}, {"id": "b", "shard": 0}]
    monkeypatch.setattr(module, "batches", lambda _: iter([batch]))
    monkeypatch.setattr(module, "JOBS", 2)
    for group in ["reference-db", "resumed-db"]:
        store = CompactShardStore(tmp_path / group / "shard-0.sqlite", {}, ["a", "b"])
        for key in ["a", "b"]:
            store.execute(key, lambda: ({"active_seconds": 3600}, b"exact"))
        store.close()
    checks = []

    def compare(a, b):
        assert a == b
        return {"array": {"exact": True}}

    result = module.compare_arms(
        tmp_path, {}, tmp_path / "unused", compare, lambda: checks.append(1)
    )
    assert result["jobs_per_arm"] == 2 and result["all_exact"] and len(checks) == 1
    before = module.prefix_digest(tmp_path / "resumed-db", 2)
    assert len(before) == 64
    with pytest.raises(ValueError, match="incomplete"):
        module.prefix_digest(tmp_path / "resumed-db", 3)
