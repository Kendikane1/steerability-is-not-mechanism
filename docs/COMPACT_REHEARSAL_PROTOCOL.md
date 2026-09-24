# P1-025 — Live compact-storage short rehearsal

Prospective engineering-only revision, 2026-09-24. Invoke the existing bounded CUDA
rehearsal with `--compact`. All P1-023 model/tokenizer, prompts, numerical tolerances,
96/49/48/0/0 forward budgets, wall deadlines, RAM/GPU/disk guards and fault point remain.
No scientific or multi-hour execution is enabled by this change.

## Storage and recovery

Each arm has one SQLite payload catalog containing its complete canonical identity and
manifest once. Each independent shard binds that identity's SHA-256 and its own at-most-16
job IDs. Retain the catalog with every shard: shards are independently verifiable with
that dependency, not standalone files. Payloads share storage only when all bytes match.
Original per-job metadata and metadata-plus-payload checksums remain reconstructible.

Use local files, one sequential writer, DELETE journals, synchronous FULL, bounded SQLite
page caches. Commit a complete checksummed bundle in the catalog before committing its
reference in the shard. Death in between can leave a harmless complete unreferenced bundle;
retain it. Never delete stale locks or silently repair corruption. Resume must reject changed
identity, missing/corrupt referenced data and altered metadata before model loading.
A successful SQLite commit is the durability boundary; process-exit tests do not establish
physical power-loss behavior of the Windows disk/controller.

The catalog has a3 GiB database ceiling and each shard64 MiB; each payload2 MiB. These are
additional bounds, not a replacement for the unchanged4 GiB total-output cap or20 GiB free
Windows reserve. Unique payloads are never discarded to satisfy a cap. Stop on overflow.
Per-shard readback holds at most16 payloads; fixture cache contains four. The existing short
supervisor holds at most48 results/arm. It is NOT the future long-run supervisor: that needs
streamed cross-arm audit, bounded telemetry/state and revised timing/storage calibration.

## Acceptance and manual handoff

Require local and Windows weight-free tests, including abrupt process exit after blob commit,
after uncommitted shard INSERT and after shard COMMIT; prior records remain exact and only
uncommitted work is recomputed. Require missing/corrupt blob, metadata and identity rejection,
writer contention refusal, and short snapshot reads while a transaction is paused.

Then run one fresh short CUDA rehearsal in p1-025/manual-compact-01. Require original comparison,
geometry, call-count, replay, identity-refusal and resource checks. Report measured catalog/shard
sizes and distinct payload counts. The inherited naive-storage calculation remains labeled as
such: it does not estimate compact long output or authorize a long run. Review evidence and
recalibrate timing/actual overhead before freezing the multi-hour protocol.

Manual launch stays in the foreground: keep the SSH terminal connected and both machines awake.
A disconnect-independent overnight launcher is a separate unverified next step. Stop after a
failure and preserve its report; no automatic reruns or migration of historical checkpoints.
