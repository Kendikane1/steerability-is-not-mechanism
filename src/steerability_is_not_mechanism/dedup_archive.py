"""Offline lossless result archive prototype; never used by an execution runner."""

import hashlib
import sqlite3
from pathlib import Path

from .shard_store import MAX_PAYLOAD_BYTES, result_hash


def read_shard(path: Path):
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ValueError("source checkpoint integrity failed")
        header = db.execute("SELECT identity FROM header WHERE id=1").fetchone()[0]
        rows = db.execute("SELECT * FROM results ORDER BY run_id").fetchall()
        for _, metadata, payload, digest in rows:
            if len(payload) > MAX_PAYLOAD_BYTES or result_hash(metadata, payload) != digest:
                raise ValueError("source row checksum or payload size mismatch")
        return header, rows
    finally:
        db.close()


def export_archive(shards: list[tuple[str, Path]], destination: Path) -> dict:
    if destination.exists():
        raise FileExistsError("archive destination already exists")
    # Reserve the filename without replacing an existing file, including an empty one.
    with destination.open("xb"):
        pass
    db = sqlite3.connect(destination)
    count = original_bytes = 0
    try:
        db.executescript(
            "PRAGMA foreign_keys=ON;"
            "CREATE TABLE blobs (hash TEXT PRIMARY KEY, payload BLOB NOT NULL);"
            "CREATE TABLE headers (arm TEXT, shard TEXT, identity TEXT NOT NULL, identity_hash TEXT, "
            "PRIMARY KEY(arm,shard));"
            "CREATE TABLE jobs (arm TEXT, shard TEXT, run_id TEXT, metadata TEXT NOT NULL, "
            "blob_hash TEXT REFERENCES blobs(hash), source_hash TEXT NOT NULL, "
            "PRIMARY KEY(arm,run_id), FOREIGN KEY(arm,shard) REFERENCES headers(arm,shard));"
        )
        for arm, source in shards:
            header, rows = read_shard(source)
            db.execute(
                "INSERT INTO headers VALUES (?,?,?,?)",
                (arm, source.name, header, hashlib.sha256(header.encode()).hexdigest()),
            )
            for key, metadata, payload, digest in rows:
                blob = hashlib.sha256(payload).hexdigest()
                existing = db.execute("SELECT payload FROM blobs WHERE hash=?", (blob,)).fetchone()
                if existing is None:
                    db.execute("INSERT INTO blobs VALUES (?,?)", (blob, payload))
                elif existing[0] != payload:
                    raise ValueError("hash collision or corrupt blob")
                db.execute(
                    "INSERT INTO jobs VALUES (?,?,?,?,?,?)",
                    (arm, source.name, key, metadata, blob, digest),
                )
                count += 1
                original_bytes += len(payload)
        db.commit()
        unique_count, unique_bytes = db.execute(
            "SELECT COUNT(*), COALESCE(SUM(LENGTH(payload)),0) FROM blobs"
        ).fetchone()
    finally:
        db.close()
    # Reopen and reconstruct every original metadata string and payload byte for byte.
    reconstructed = read_archive(destination)
    for arm, source in shards:
        _, rows = read_shard(source)
        for key, metadata, payload, digest in rows:
            if reconstructed[(arm, key)] != (source.name, metadata, payload, digest):
                raise ValueError("archive reconstruction differs from source")
    if len(reconstructed) != count:
        raise ValueError("archive result count mismatch")
    return {
        "jobs": count,
        "original_payload_bytes": original_bytes,
        "unique_payloads": unique_count,
        "unique_payload_bytes": unique_bytes,
        "archive_bytes": destination.stat().st_size,
        "exact_reconstruction": True,
    }


def read_archive(path: Path) -> dict:
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ValueError("archive integrity failed")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("missing archive blob or header")
        for identity, digest in db.execute("SELECT identity,identity_hash FROM headers"):
            if hashlib.sha256(identity.encode()).hexdigest() != digest:
                raise ValueError("archive header checksum mismatch")
        for digest, payload in db.execute("SELECT * FROM blobs"):
            if hashlib.sha256(payload).hexdigest() != digest:
                raise ValueError("archive blob checksum mismatch")
        result = {}
        for arm, shard, key, meta, payload, digest in db.execute(
            "SELECT j.arm,j.shard,j.run_id,j.metadata,b.payload,j.source_hash "
            "FROM jobs j JOIN blobs b ON b.hash=j.blob_hash"
        ):
            if result_hash(meta, payload) != digest:
                raise ValueError("reconstructed row checksum mismatch")
            result[(arm, key)] = (shard, meta, payload, digest)
        return result
    finally:
        db.close()
