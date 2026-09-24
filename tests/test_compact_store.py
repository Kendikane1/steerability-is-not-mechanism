"""No-model durability tests, including real process exit without Python cleanup."""

import os
import sqlite3
import subprocess
import sys

import pytest

from steerability_is_not_mechanism.compact_store import CompactShardStore


def test_shared_payload_exact_reopen(tmp_path):
    for i in range(3):
        store = CompactShardStore(tmp_path / f"shard-{i}.sqlite", {"manifest": "fixed"}, ["a", "b"])
        for key in ["a", "b"]:
            assert store.execute(key, lambda key=key: ({"id": key}, b"identical"))
        store.close()
    store = CompactShardStore(tmp_path / "shard-0.sqlite", {"manifest": "fixed"}, ["a", "b"])
    assert store.pool.execute("SELECT COUNT(*) FROM blobs").fetchone() == (1,)
    assert store.completed()["b"][0] == {"id": "b"}
    assert not store.execute("a", lambda: pytest.fail("recomputed"))
    store.close()
    with pytest.raises(ValueError, match="identity"):
        CompactShardStore(tmp_path / "shard-0.sqlite", {"manifest": "changed"}, ["a", "b"])


@pytest.mark.parametrize("boundary", ["after_blob", "before_commit", "after_commit"])
def test_process_death(tmp_path, boundary):
    path = tmp_path / "shard.sqlite"
    store = CompactShardStore(path, {}, ["a", "b"])
    store.execute("a", lambda: ({}, b"prior"))
    digest = store.completed()["a"][2]
    store.close()
    script = """
import os, sys
from pathlib import Path
from steerability_is_not_mechanism.compact_store import CompactShardStore
s = CompactShardStore(Path(sys.argv[1]), {}, ['a','b'])
kwargs = {sys.argv[2]: lambda: os._exit(73)} if sys.argv[2] != 'after_commit' else {}
s.execute('b', lambda: ({}, b'new'), **kwargs)
os._exit(73)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(path), boundary], env=os.environ.copy(), timeout=20
    )
    assert result.returncode == 73
    store = CompactShardStore(path, {}, ["a", "b"])
    assert store.completed()["a"][2] == digest
    assert ("b" in store.completed()) == (boundary == "after_commit")
    assert store.execute("b", lambda: ({}, b"new")) == (boundary != "after_commit")
    assert store.pool.execute("SELECT COUNT(*) FROM blobs").fetchone() == (2,)
    store.close()


@pytest.mark.parametrize("damage", ["blob", "missing", "metadata", "header"])
def test_corruption_refused(tmp_path, damage):
    path = tmp_path / "shard.sqlite"
    store = CompactShardStore(path, {}, ["a"])
    store.execute("a", lambda: ({}, b"keep"))
    assert store.db is not None
    if damage == "blob":
        store.pool.execute("UPDATE blobs SET payload=X'00'")
    elif damage == "missing":
        store.pool.execute("DELETE FROM blobs")
    elif damage == "metadata":
        store.db.execute("UPDATE results SET metadata='{} changed'")
    else:
        store.db.execute("UPDATE header SET identity='changed'")
    store.close()
    with pytest.raises(ValueError):
        CompactShardStore(path, {}, ["a"])


def test_contention_and_scope(tmp_path):
    path = tmp_path / "shard.sqlite"
    first = CompactShardStore(path, {}, ["a"])
    second = CompactShardStore(path, {}, ["a"])
    assert first.db is not None
    first.db.execute("BEGIN IMMEDIATE")
    with pytest.raises(sqlite3.OperationalError):
        second.execute("a", lambda: pytest.fail("second writer computed"))
    first.db.execute("ROLLBACK")
    with pytest.raises(ValueError, match="outside"):
        first.execute("b", lambda: pytest.fail("wrong scope"))
    first.close()
    second.close()


def test_snapshot_sees_only_committed_rows_while_paused(tmp_path):
    from steerability_is_not_mechanism.compact_store import snapshot

    identity = {"manifest": [{"id": "a", "shard": 0}, {"id": "b", "shard": 0}]}
    store = CompactShardStore(tmp_path / "shard-0.sqlite", identity, ["a", "b"])
    store.execute("a", lambda: ({}, b"prior"))

    def paused():
        assert set(snapshot(tmp_path, identity)) == {"a"}

    store.execute("b", lambda: ({}, b"new"), paused)
    assert set(snapshot(tmp_path, identity)) == {"a", "b"}
    store.close()


@pytest.mark.parametrize("target", ["pool_header", "shard_header", "catalog"])
def test_missing_identity_never_repaired(tmp_path, target):
    path = tmp_path / "shard.sqlite"
    store = CompactShardStore(path, {}, ["a"])
    store.execute("a", lambda: ({}, b"keep"))
    assert store.db is not None
    if target == "pool_header":
        store.pool.execute("DELETE FROM header")
    elif target == "shard_header":
        store.db.execute("DELETE FROM header")
    store.close()
    if target == "catalog":
        (tmp_path / "payloads.sqlite").unlink()
    with pytest.raises(ValueError):
        CompactShardStore(path, {}, ["a"])
