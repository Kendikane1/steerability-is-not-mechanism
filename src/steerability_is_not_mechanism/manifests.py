"""Deterministic, resumable experiment manifest primitives."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field


class ManifestRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    item_id: str
    condition: str
    intervention: str
    seed: int = Field(ge=0)


def shard_for(run_id: str, shard_count: int) -> int:
    if shard_count < 1:
        raise ValueError("shard_count must be positive")
    digest = hashlib.sha256(run_id.encode()).digest()
    return int.from_bytes(digest[:8], "big") % shard_count


def manifest_sha256(rows: Iterable[ManifestRow]) -> str:
    canonical = "\n".join(row.model_dump_json() for row in sorted(rows, key=lambda row: row.run_id))
    return hashlib.sha256(canonical.encode()).hexdigest()


def canonical_manifest_line(row: ManifestRow) -> str:
    return json.dumps(row.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
