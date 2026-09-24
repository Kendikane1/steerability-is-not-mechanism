import sqlite3

import pytest

from steerability_is_not_mechanism.dedup_archive import export_archive, read_archive
from steerability_is_not_mechanism.shard_store import ShardStore


def fixture(tmp_path):
    path = tmp_path / "source.sqlite"
    store = ShardStore(path, {"synthetic": True}, ["a", "b", "c"])
    for name, payload in [("a", b"identical"), ("b", b"identical"), ("c", b"different")]:
        store.execute(name, lambda name=name, payload=payload: ({"id": name}, payload))
    store.close()
    return path


def test_exact_bytes_preserved_and_different_results_not_merged(tmp_path):
    source = fixture(tmp_path)
    original = source.read_bytes()
    target = tmp_path / "archive.sqlite"
    result = export_archive([("reference", source)], target)
    assert result["jobs"] == 3 and result["unique_payloads"] == 2
    restored = read_archive(target)
    assert restored[("reference", "a")][2] == b"identical"
    assert restored[("reference", "c")][2] == b"different"
    assert source.read_bytes() == original
    with pytest.raises(FileExistsError):
        export_archive([("reference", source)], target)


@pytest.mark.parametrize("corruption", ["blob", "missing", "metadata", "header"])
def test_archive_detects_corruption(tmp_path, corruption):
    source = fixture(tmp_path)
    target = tmp_path / "archive.sqlite"
    export_archive([("reference", source)], target)
    db = sqlite3.connect(target)
    if corruption == "blob":
        db.execute("UPDATE blobs SET payload=?", (b"corrupt",))
    elif corruption == "missing":
        db.execute("DELETE FROM blobs")
    elif corruption == "header":
        db.execute("UPDATE headers SET identity='{}'")
    else:
        db.execute("UPDATE jobs SET metadata='{}'")
    db.commit()
    db.close()
    with pytest.raises(ValueError):
        read_archive(target)


def test_corrupt_source_refused(tmp_path):
    source = fixture(tmp_path)
    db = sqlite3.connect(source)
    db.execute("UPDATE results SET sha256='incorrect'")
    db.commit()
    db.close()
    with pytest.raises(ValueError, match="source row"):
        export_archive([("reference", source)], tmp_path / "archive.sqlite")
