# P1-024 — Rehearsal audit and lossless storage experiment

## Result

The completed CUDA rehearsal passed an independent offline audit. A lossless archive prototype
reconstructed all96 job records exactly, including original metadata and saved result bytes.
The original evidence was preserved. No model inference was run during this review.

| Measurement | Result |
| --- | --- |
| Rehearsal calls |96 reference +49 interrupted +48 resumed; replay/incompatible probes0 |
| Completed jobs |48 per arm;24 pre-interruption committed records preserved |
| Across-arm array comparisons |192; all exactly equal |
| Original six checkpoint files |89,235,456 bytes (85.10 MiB) |
| Distinct complete result bundles |4 across96 job records |
| Prototype archive |4,042,752 bytes (3.86 MiB), including metadata and headers |
| Exact reconstruction |Every original metadata string, result payload and row checksum matched |
| Source evidence |All25 file hashes verified before and after transformation |

The audit checked source identities from a separately retained snapshot, console/checkpoint
hashes, SQLite integrity, repeated arrays, intervention geometry, retained committed checksums,
forward budgets and the original timing/storage calculation. The source snapshot includes a
Windows-only ignored notebook checkpoint already present in the run identity; it was preserved
and hashed, not silently excluded or added to active local code.

Worker telemetry recorded at least4,202,692,608 bytes free GPU and1,377,935,360 bytes available
host RAM; allocator peak3,162,115,584 bytes. These are short-run telemetry results, not guarantees
of instantaneous system peaks or multi-hour headroom.

## What deduplication does

Each original NPZ bundle contains the complete arrays for one job. Store a bundle under its
SHA-256 only once. Each job retains its own arm/shard/ID, original metadata, original result
checksum and reference to the bundle. Identical bytes may share storage; merely similar values
never do. Every distinct bundle must remain stored, even if its numbers pass a tolerance check.
This prototype does not round numbers, omit arrays, sample repetitions or recompute old results.

Tests reject corrupt source rows, corrupt/missing archive blobs, altered metadata/headers and
an existing destination. Reopening the archive reconstructs every source result exactly.

## Conditional long-run estimate

The original calibration proposed22,223 cycles per arm (177,784 jobs across both arms), based
on the fastest post-warm-up cycle of about0.405 seconds. Naive full retention projects184.022 GiB.
The prospective shared-bundle layout projects **1.44 GiB**, below the unchanged4 GiB cap, assuming:

- Result bundles continue repeating byte-identically. Any new distinct result consumes more space.
- Store the complete immutable job manifest once; each shard binds its hash. Do not embed the
  complete growing manifest in every shard header, which would multiply storage unnecessarily.
- Budget2,067 bytes/job for metadata/references,15,943 bytes/shard for headers,1,024 bytes/job for
  the global manifest; double these projected totals and add256 MiB for logs/journals.
- Actual runtime storage still has a hard4 GiB cap and the Windows20 GiB disk reserve.

These are explicit estimates for a proposed layout, not measured multi-hour output or a newly
frozen long-run protocol. They are not a worst-case bound if every result becomes unique.

## Next engineering step

Implement a live shared-bundle store with bounded memory, durable blob publication before
checkpoint commit, corruption detection, independent shard verification and interruption/recovery
tests. A crash may leave an unreferenced blob; it must never leave a committed job referring to
missing or incomplete data. Keep the complete manifest and all identity bindings immutable.

The current offline prototype reads small result sets into memory. Do not apply its all-results
readback directly to a long run: stream comparisons, hash files incrementally and bound caches.
Validate actual metadata/journal/log overhead and a fresh short rehearsal of the changed writer
before freezing or starting either multi-hour arm. Existing numerical/resource/scientific guards
remain unchanged. No model-backed storage rehearsal or multi-hour run occurred in P1-024.

## Reproduction and artifacts

Use the project environment, with the retrieved evidence and original source snapshot present:

```sh
uv run --locked --offline python notebooks/audit_remote_rehearsal.py \
  --input-dir outputs/phase1/p1-024/evidence/manual-rehearsal-03 \
  --source-root outputs/phase1/p1-024/source-snapshot \
  --output-dir outputs/phase1/p1-024/audit-new
uv run --locked --offline python notebooks/check_dedup_archive.py \
  --input-dir outputs/phase1/p1-024/evidence/manual-rehearsal-03 \
  --audit outputs/phase1/p1-024/audit-new/audit.json \
  --output-dir outputs/phase1/p1-024/dedup-new
```

Existing results: `audit-02/audit.json`, `dedup/report.json` and `dedup/results.sqlite` under
ignored `outputs/phase1/p1-024/`. Archive SHA256:
`9a48628a75b899b93b1daab76bd480a1763a5207db7f6510f8dd7f42787f4684`.
Original supervisor report SHA256:
`f4cdf176500bfe897479fab8eb60cb0b18b80d80a8f9160911c8a5d81b1a018e`.
