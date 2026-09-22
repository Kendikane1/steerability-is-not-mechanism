"""Small local SQLite shard store with atomic completion and strict resume identity."""

import hashlib
import json
import sqlite3
from collections.abc import Callable
from pathlib import Path

MAX_PAYLOAD_BYTES = 2 * 1024**2
MAX_DATABASE_BYTES = 64 * 1024**2


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def result_hash(metadata: str, payload: bytes) -> str:
    return hashlib.sha256(metadata.encode() + b"\x00" + payload).hexdigest()


class ShardStore:
    """One writer per shard; a unique ID becomes complete only on transaction commit.

    No stale-lock deletion, replacement writes or automatic identity migration. The operating
    system releases SQLite locks when a process dies. Files must live on a local filesystem.
    """

    def __init__(self, path: Path, identity: dict, run_ids: list[str]):
        if len(run_ids) != len(set(run_ids)) or not run_ids:
            raise ValueError("empty or duplicate manifest IDs")
        if path.is_symlink():
            raise ValueError("checkpoint symlinks are forbidden")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.ids = frozenset(run_ids)
        self.identity = canonical({"schema": 1, "identity": identity, "run_ids": sorted(run_ids)})
        self.db = sqlite3.connect(path, timeout=0, isolation_level=None)
        try:
            self.db.execute("PRAGMA journal_mode=DELETE")
            self.db.execute("PRAGMA synchronous=FULL")
            page_size = self.db.execute("PRAGMA page_size").fetchone()[0]
            limit = MAX_DATABASE_BYTES // page_size
            actual_limit = self.db.execute(f"PRAGMA max_page_count={limit}").fetchone()[0]
            if actual_limit > limit:
                raise ValueError("existing checkpoint exceeds database budget")
            self.db.execute("BEGIN IMMEDIATE")
            tables = {
                r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            if not tables:
                self.db.execute(
                    "CREATE TABLE header (id INTEGER PRIMARY KEY CHECK(id=1), identity TEXT NOT NULL)"
                )
                self.db.execute(
                    "CREATE TABLE results (run_id TEXT PRIMARY KEY, metadata TEXT NOT NULL, payload BLOB NOT NULL, sha256 TEXT NOT NULL)"
                )
                self.db.execute("INSERT INTO header VALUES (1,?)", (self.identity,))
            elif tables != {"header", "results"}:
                raise ValueError("unrecognized checkpoint schema")
            self.validate()
            self.db.execute("COMMIT")
        except BaseException:
            self.db.close()
            raise

    def validate(self) -> None:
        header = self.db.execute("SELECT identity FROM header WHERE id=1").fetchone()
        if header != (self.identity,):
            raise ValueError("incompatible resume identity")
        for run_id, metadata, payload, digest in self.db.execute("SELECT * FROM results"):
            if run_id not in self.ids:
                raise ValueError("checkpoint has an unexpected completed ID")
            if len(payload) > MAX_PAYLOAD_BYTES or result_hash(metadata, payload) != digest:
                raise ValueError("completed result checksum or size mismatch")
            canonical(json.loads(metadata))

    def completed(self) -> dict[str, tuple[dict, bytes, str]]:
        self.validate()
        return {
            r[0]: (json.loads(r[1]), r[2], r[3])
            for r in self.db.execute("SELECT * FROM results ORDER BY run_id")
        }

    def execute(
        self,
        run_id: str,
        compute: Callable[[], tuple[dict, bytes]],
        before_commit: Callable[[], None] = lambda: None,
    ) -> bool:
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
                raise ValueError("result payload exceeds fixed budget or is not bytes")
            serialized = canonical(metadata)
            digest = result_hash(serialized, payload)
            self.db.execute(
                "INSERT INTO results VALUES (?,?,?,?)", (run_id, serialized, payload, digest)
            )
            before_commit()  # Fault-injection boundary: row exists but is NOT committed.
            self.db.execute("COMMIT")
            return True
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def close(self) -> None:
        self.db.close()
