# Local synthetic shard/resume check — P1-016

This is milestone 4 engineering on the existing Qwen3-0.6B synthetic pair. It does not authorize
scientific execution. Exact settings remain in `local_model_engineering.yaml`; the separate
`local_resume.yaml` permits only four fixed jobs, two shards, and at most eight forwards per worker.

## What is being resumed?

We resume a list of completed experimental jobs. We do not save a partially computed transformer
forward pass or reload optimizer/model state. Each job can be recomputed from the pinned model,
fixed prompt(s), direction and seed without results from any other job.

| Job | Shard | Forwards | Saved result |
|---|---:|---:|---|
| `synthetic-resume-high_capture` | 1 | 1 | High-context logits and activation |
| `synthetic-resume-high_edit` | 0 | 3 | Own source/donor captures, dense edit, scores and geometry |
| `synthetic-resume-low_capture` | 0 | 1 | Low-context logits and activation |
| `synthetic-resume-low_edit` | 0 | 3 | Own source/donor captures, reverse dense edit, scores and geometry |

Assignment uses the existing SHA-256 ID function with two shards; jobs run in sorted ID order.
The uneven 3/1 split is intentional acceptance of a tiny deterministic hash partition. We did not
search for IDs to obtain a balanced or favorable result. This is one item with four technical jobs.

## The completion boundary

Each shard owns a SQLite database. A worker:

1. Opens and validates the exact stored resume identity and completed-row checksums.
2. Begins an immediate writer transaction for a job.
3. Rechecks completion under that lock. If complete, skips without loading the model.
4. Otherwise computes the self-contained job and validates its outputs.
5. Inserts metadata, array payload and checksum together, using a unique job ID.
6. Commits. Only now is that job complete.

If the process dies before commit, SQLite rolls back the partial transaction on recovery. The job
is rerun. The guarantee is one committed output per ID, not that unfinished computations are
attempted only once. There is no upsert, replacement write or stale-lock deletion.

One writer owns a shard transaction throughout computation. Another same-shard writer fails
closed immediately. Different shards have separate databases, but this Mac test runs them
sequentially to avoid loading multiple models into 8 GiB unified memory.

SQLite uses a rollback journal and synchronous FULL. These settings support local transactional
recovery; our test is not proof of durability through a power failure or arbitrary filesystem fault.

## Identity and integrity

The stored identity includes the fixed ordered manifest, seed and prompt settings; source,
protocol and lockfile hashes; actual device; Python/platform/packages; SQLite version; and relevant
offline/determinism environment settings. Scientific loader guards remain unchanged.

Changed settings/code/device are refused before model construction. A Git commit ID alone is
insufficient when work is uncommitted, so content hashes identify actual source bytes. Moving an
unchanged request file to another path does not change its meaning; its validated values do.

Completed-row checksums cover canonical JSON metadata and NumPy array bytes. Array loading
forbids pickle. The current limits are 2 MiB array payload per job and 64 MiB per shard database.
These limits suit this fixture; a larger scientific storage design remains separate work.

A checksum detects changed bytes, not whether the underlying scientific method is correct.
Raw databases and run artifacts are ignored local outputs, not automatically backed up by Git.

## Acceptance experiment

The supervisor creates a new output directory and launches fresh local worker processes:

1. Complete reference shards 0 and 1 without interruption.
2. In another run, commit shard 0's first job, then pause after the second job's INSERT but before
   COMMIT. Confirm a rollback journal exists and only the first result is visible to another reader.
3. Send SIGKILL to that owned worker. Preserve its last attempt record and record termination in
   the supervisor report. Do not rewrite the interrupted record as a graceful completion.
4. Recover and resume shard 0 in a fresh process, then run shard 1. Check the earlier committed
   hash is unchanged and its job is skipped; recompute the interrupted job and finish the remainder.
5. Reopen the complete shard. Require zero model load and zero forwards.
6. Try incompatible device-request metadata. Require rejection with zero model load/forwards.
7. Match all job IDs and all saved arrays against the reference, including logits, activations,
   donor vectors, applied edits and directions. Use the predeclared element and margin tolerances,
   and separately report exact equality. Recheck raw-logit margin identities and hook/geometry gates.

Each worker has a 180-second supervisor deadline. Failure stops the check and preserves artifacts;
there is no automatic tolerance change or retry-until-success. Unit tests additionally cover
rollback, corrupt payloads, duplicate/out-of-shard IDs, writer contention and changed source,
tokenizer, seed, dtype, package, device and manifest identities.

## Reproduction

Requires the verified local tokenizer/weights and the locked environment, already established in
P1-005 through P1-015. Use a fresh process and a new output directory:

```sh
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 \
HF_DEACTIVATE_ASYNC_LOAD=1 uv run --locked --offline python notebooks/check_local_resume.py \
  --output-dir outputs/phase1/resume-reproduction-01
```

`run_local_resume.py` is the worker; `check_local_resume.py` supervises the comparison and fault
injection. `shard_store.py` handles transactions/integrity; `resume_jobs.py` defines the jobs.
See P1-016 in `RESEARCH_LOG.md` for measured outcomes and immutable artifact identities.

## Limits of the result

This short, same-machine local check can establish process-interruption recovery for these jobs.
It does not establish multi-hour reliability, different-machine/device equality, network/shared
filesystem behavior, remote CUDA resumption, power-loss durability or scientific readiness.
Milestone 5 still requires a consolidated engineering review; pre-pilot decisions remain open.


## Measured outcome, 2026-09-22

The supervised check passed in about three minutes, with no unexpected failures. All four jobs
completed once per final run and all 16 saved arrays matched the uninterrupted reference exactly.
Maximum element and margin differences were zero. The killed worker had a 12,824-byte rollback
journal and only its first job committed. Fresh resume skipped that job, preserved its hash, and
recomputed the unfinished job before completing the last job.

There were 17 model forward attempts: 8 reference, 8 producing the final resumed outputs, and
1 discarded by the intentional interruption. Completed replay performed zero forwards and did
not load the model. Changed-device request identity was rejected before loading. Unit/static
verification passed: 136 tests, locked offline sync, lint/format, basedpyright (including explicit
worker/supervisor checks), and the original synthetic smoke test.

Each run's shard databases were 3,117,056 and 630,784 bytes. The model-backed report and its
artifact hashes are in `outputs/phase1/p1-016/check-01/report.json`; research-log entry P1-016
records the report checksum and interpretation. These bounded results do not remove the limits
listed above.
