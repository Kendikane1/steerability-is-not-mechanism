"""Transaction/integrity failure cases, no model or network."""

import sqlite3

import pytest

from steerability_is_not_mechanism.shard_store import MAX_PAYLOAD_BYTES, ShardStore


def test_commit_reopen_skip_and_rollback(tmp_path):
    path = tmp_path / "shard.sqlite"
    store = ShardStore(path, {"device": "cpu"}, ["a", "b"])
    assert store.execute("a", lambda: ({"margin": 1.0}, b"complete"))
    digest = store.completed()["a"][2]

    def fail():
        raise RuntimeError("before commit")

    with pytest.raises(RuntimeError):
        store.execute("b", lambda: ({}, b"partial"), fail)
    assert set(store.completed()) == {"a"}
    store.close()
    store = ShardStore(path, {"device": "cpu"}, ["a", "b"])
    assert not store.execute("a", lambda: pytest.fail("completed job recomputed"))
    assert store.completed()["a"][2] == digest
    assert store.execute("b", lambda: ({}, b"recomputed"))
    assert set(store.completed()) == {"a", "b"}
    store.close()


@pytest.mark.parametrize("change", ["device", "manifest"])
def test_identity_mismatch_preserves_completed_result(tmp_path, change):
    path = tmp_path / "shard.sqlite"
    store = ShardStore(path, {"device": "cpu"}, ["a"])
    store.execute("a", lambda: ({}, b"keep"))
    store.close()
    with pytest.raises(ValueError, match="identity"):
        ShardStore(
            path,
            {"device": "mps" if change == "device" else "cpu"},
            ["a", "b"] if change == "manifest" else ["a"],
        )
    store = ShardStore(path, {"device": "cpu"}, ["a"])
    assert store.completed()["a"][1] == b"keep"
    store.close()


def test_corrupted_result_rejected(tmp_path):
    path = tmp_path / "shard.sqlite"
    store = ShardStore(path, {}, ["a"])
    store.execute("a", lambda: ({}, b"keep"))
    store.db.execute("UPDATE results SET payload=? WHERE run_id='a'", (b"corrupt",))
    with pytest.raises(ValueError, match="checksum"):
        store.completed()
    store.close()
    with pytest.raises(ValueError, match="checksum"):
        ShardStore(path, {}, ["a"])


def test_writer_contention_never_starts_second_compute(tmp_path):
    path = tmp_path / "shard.sqlite"
    first = ShardStore(path, {}, ["a"])
    second = ShardStore(path, {}, ["a"])
    first.db.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            second.execute("a", lambda: pytest.fail("concurrent computation"))
    finally:
        first.db.execute("ROLLBACK")
        first.close()
    assert second.execute("a", lambda: ({}, b"ok"))
    second.close()


def test_manifest_scope_and_budget(tmp_path):
    with pytest.raises(ValueError, match="duplicate"):
        ShardStore(tmp_path / "bad.sqlite", {}, ["a", "a"])
    store = ShardStore(tmp_path / "good.sqlite", {}, ["a"])
    with pytest.raises(ValueError, match="outside"):
        store.execute("b", lambda: pytest.fail("wrong shard"))
    with pytest.raises(ValueError, match="budget"):
        store.execute("a", lambda: ({}, b"x" * (MAX_PAYLOAD_BYTES + 1)))
    assert not store.completed()
    store.close()


@pytest.mark.parametrize(
    "field", ["source_hash", "tokenizer_revision", "seed", "dtype", "packages"]
)
def test_changed_reproducibility_fields_rejected(tmp_path, field):
    path = tmp_path / "shard.sqlite"
    identity = {
        "source_hash": "abc",
        "tokenizer_revision": "rev",
        "seed": 1729,
        "dtype": "float32",
        "packages": "locked",
    }
    store = ShardStore(path, identity, ["a"])
    store.close()
    changed = dict(identity)
    changed[field] = "changed"
    with pytest.raises(ValueError, match="identity"):
        ShardStore(path, changed, ["a"])


def test_existing_database_over_budget_is_rejected_without_data_loss(tmp_path, monkeypatch):
    import steerability_is_not_mechanism.shard_store as module

    path = tmp_path / "shard.sqlite"
    store = ShardStore(path, {}, ["a"])
    store.execute("a", lambda: ({}, b"x" * 65536))
    digest = store.completed()["a"][2]
    store.close()
    with monkeypatch.context() as patcher:
        patcher.setattr(module, "MAX_DATABASE_BYTES", 16384)
        with pytest.raises(ValueError, match="database budget"):
            ShardStore(path, {}, ["a"])
    reopened = ShardStore(path, {}, ["a"])
    assert reopened.completed()["a"][2] == digest
    reopened.close()
