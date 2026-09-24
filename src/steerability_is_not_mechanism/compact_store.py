"""Live lossless payload sharing: durable blob commit precedes shard completion.

One sequential writer, local filesystem only. Shards contain at most 16 jobs; the
shared catalog stores the full identity/manifest once. No all-run payload cache.
"""

import hashlib
import json
import sqlite3
from pathlib import Path

from .shard_store import MAX_DATABASE_BYTES, MAX_PAYLOAD_BYTES, canonical, result_hash


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def connect(path: Path, budget: int):
    if path.is_symlink():
        raise ValueError("checkpoint symlinks forbidden")
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=0, isolation_level=None)
    try:
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA cache_size=-2048")
        pages = budget // db.execute("PRAGMA page_size").fetchone()[0]
        if db.execute(f"PRAGMA max_page_count={pages}").fetchone()[0] > pages:
            raise ValueError("database budget exceeded")
        if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ValueError("checkpoint integrity failed")
        return db
    except BaseException:
        db.close()
        raise


class CompactShardStore:
    def __init__(self, path: Path, identity: dict, run_ids: list[str]):
        if not run_ids or len(run_ids) > 16 or len(set(run_ids)) != len(run_ids):
            raise ValueError("shard requires 1–16 unique IDs")
        self.ids = frozenset(run_ids)
        full = canonical({"schema": "compact-v1", "identity": identity})
        digest = hashlib.sha256(full.encode()).hexdigest()
        self.identity = canonical({"catalog_sha256": digest, "run_ids": sorted(run_ids)})
        catalog = path.parent / "payloads.sqlite"
        if path.exists() and not catalog.exists():
            raise ValueError("missing payload catalog")
        self.pool = connect(catalog, 3 * 1024**3)
        self.db = None
        try:
            self.pool.execute("BEGIN IMMEDIATE")
            pool_existing = bool(
                self.pool.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone()
            )
            self.pool.execute("CREATE TABLE IF NOT EXISTS header (identity TEXT NOT NULL)")
            self.pool.execute(
                "CREATE TABLE IF NOT EXISTS blobs (hash TEXT PRIMARY KEY, payload BLOB NOT NULL)"
            )
            rows = self.pool.execute("SELECT identity FROM header").fetchall()
            if not rows and not pool_existing:
                self.pool.execute("INSERT INTO header VALUES (?)", (full,))
            elif rows != [(full,)]:
                raise ValueError("incompatible resume identity")
            self.pool.execute("COMMIT")
            self.db = connect(path, MAX_DATABASE_BYTES)
            self.db.execute("BEGIN IMMEDIATE")
            shard_existing = bool(
                self.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone()
            )
            self.db.execute("CREATE TABLE IF NOT EXISTS header (identity TEXT NOT NULL)")
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS results (run_id TEXT PRIMARY KEY, metadata TEXT NOT NULL, blob_hash TEXT NOT NULL, sha256 TEXT NOT NULL)"
            )
            rows = self.db.execute("SELECT identity FROM header").fetchall()
            if not rows and not shard_existing:
                self.db.execute("INSERT INTO header VALUES (?)", (self.identity,))
            elif rows != [(self.identity,)]:
                raise ValueError("incompatible resume identity")
            self.validate()
            self.db.execute("COMMIT")
        except BaseException:
            self.close()
            raise

    def records(self):
        assert self.db is not None
        if self.db.execute("SELECT identity FROM header").fetchall() != [(self.identity,)]:
            raise ValueError("incompatible resume identity")
        for key, meta, blob, digest in self.db.execute("SELECT * FROM results ORDER BY run_id"):
            if key not in self.ids:
                raise ValueError("unexpected completed ID")
            row = self.pool.execute("SELECT payload FROM blobs WHERE hash=?", (blob,)).fetchone()
            if row is None:
                raise ValueError("missing payload")
            payload = row[0]
            if (
                len(payload) > MAX_PAYLOAD_BYTES
                or hashlib.sha256(payload).hexdigest() != blob
                or result_hash(meta, payload) != digest
            ):
                raise ValueError("result checksum or size mismatch")
            yield key, (json.loads(meta), payload, digest)

    def validate(self):
        for _ in self.records():
            pass

    def completed(self):
        return dict(self.records())  # Bounded to at most 16 payloads, never all shards.

    def execute(self, run_id, compute, before_commit=lambda: None, after_blob=lambda: None):
        assert self.db is not None
        if run_id not in self.ids:
            raise ValueError("job is outside this shard")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.validate()
            if self.db.execute("SELECT 1 FROM results WHERE run_id=?", (run_id,)).fetchone():
                self.db.execute("COMMIT")
                return False
            metadata, payload = compute()
            if not isinstance(payload, bytes) or len(payload) > MAX_PAYLOAD_BYTES:
                raise ValueError("result payload exceeds budget or is not bytes")
            meta = canonical(metadata)
            blob = hashlib.sha256(payload).hexdigest()
            self.pool.execute("BEGIN IMMEDIATE")
            existing = self.pool.execute(
                "SELECT payload FROM blobs WHERE hash=?", (blob,)
            ).fetchone()
            if existing is None:
                self.pool.execute("INSERT INTO blobs VALUES (?,?)", (blob, payload))
            elif existing != (payload,):
                raise ValueError("hash collision or corrupt blob")
            self.pool.execute("COMMIT")  # Durable before any committed reference can exist.
            after_blob()  # A crash here may leave an unreferenced complete blob; retain it.
            self.db.execute(
                "INSERT INTO results VALUES (?,?,?,?)",
                (run_id, meta, blob, result_hash(meta, payload)),
            )
            before_commit()
            self.db.execute("COMMIT")
            return True
        except BaseException:
            for db in (self.db, self.pool):
                if db.in_transaction:
                    db.execute("ROLLBACK")
            raise

    def close(self):
        if self.db is not None:
            self.db.close()
        self.pool.close()


def snapshot(folder: Path, identity: dict):
    """Read a paused short worker without taking its writer lock; at most 48 rows."""
    full = canonical({"schema": "compact-v1", "identity": identity})
    digest = hashlib.sha256(full.encode()).hexdigest()
    pool = sqlite3.connect((folder / "payloads.sqlite").resolve().as_uri() + "?mode=ro", uri=True)
    result = {}
    try:
        if pool.execute("SELECT identity FROM header").fetchall() != [(full,)]:
            raise ValueError("incompatible resume identity")
        for shard in range(3):
            path = folder / f"shard-{shard}.sqlite"
            if not path.exists():
                continue
            ids = [r["id"] for r in identity["manifest"] if r["shard"] == shard]
            db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                expected = canonical({"catalog_sha256": digest, "run_ids": sorted(ids)})
                if db.execute("SELECT identity FROM header").fetchall() != [(expected,)]:
                    raise ValueError("incompatible resume identity")
                if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise ValueError("checkpoint integrity failed")
                for key, meta, blob, checksum in db.execute("SELECT * FROM results"):
                    row = pool.execute("SELECT payload FROM blobs WHERE hash=?", (blob,)).fetchone()
                    if row is None or key not in ids or key in result:
                        raise ValueError("missing payload or invalid ID")
                    payload = row[0]
                    if (
                        len(payload) > MAX_PAYLOAD_BYTES
                        or hashlib.sha256(payload).hexdigest() != blob
                        or result_hash(meta, payload) != checksum
                    ):
                        raise ValueError("result checksum mismatch")
                    result[key] = (json.loads(meta), payload, checksum)
            finally:
                db.close()
        return result
    finally:
        pool.close()
