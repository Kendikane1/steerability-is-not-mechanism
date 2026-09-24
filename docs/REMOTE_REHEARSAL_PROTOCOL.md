# P1-023 — bounded CUDA rehearsal

Authorized by the user's continuation after P1-022. Engineering only: pinned Qwen3-0.6B,
float32, same prompts/template/block13/dense synthetic direction, strict CUDA settings and
numerical/geometry limits. No new weights, scientific items, pilot or locked work.

Question: does one loaded model remain stable across repeated jobs and shard boundaries, and
is full-array retention feasible for the proposed multi-hour test? Prediction: numerical
checks pass; fast CUDA throughput may make the unchanged4 GiB retained-output cap infeasible.

## Frozen workload and acceptance

Separate `remote_cuda_rehearsal_v1` request:12 cycles,48 jobs,96 maximum forwards per worker.
Use the existing deterministic rehearsal manifest: four fixed fixtures per cycle,16 jobs per
shard, three sequential shards. Keep one model loaded across shards. Reference96 calls;
comparison49 calls before intentional termination plus48 after restart =193 attempts total.
Pause at manifest index24 after INSERT/before COMMIT, verify24 prior committed IDs and journal,
validate worker/launcher ownership and terminate only that process tree. Preserve original
checksums on resume, skip completed rows, recompute the unfinished transaction, require48 unique
IDs per arm. Compare all saved arrays within each arm and across arms using frozen element
1e-5 absolute+relative and margin1e-4 tolerances; report exact equality. Existing geometry,
unaltered token positions and hook cleanup remain mandatory. Completed replay and changed-
identity probes must perform zero model loads/forwards. No automatic retry after failure.

Identity binds complete manifest, source/worker/supervisor/request/protocol/lock hashes,
Python/platform/package/runtime settings, pinned model/tokenizer and device. Prior short-run
requests retain their original budgets; old checkpoints are not migrated. Full arrays retained;
2 MiB payload/job and64 MiB/shard remain unchanged.

## Resources and supervision

Retain P1-022 Windows resource limits: startup GPU free4 GiB and available physical RAM/commit
1 GiB; runtime GPU free1 GiB, RAM/commit512 MiB, memory load below95%; disk free20 GiB throughout.
Stop at4 GiB total rehearsal outputs. Worker samples GPU/host resources about once per second
and at boundaries; supervisor samples host resources, disk, progress and worker telemetry about
once per second. Unavailable readings fail. Required worker samples older than5 seconds fail;
sample duration over5 seconds fails. GPU allocator peaks and sampled minima are different metrics.

Reference arm wall cap600 seconds; interrupted+resumed arm shares600 seconds including recovery.
No committed progress for180 seconds fails, including loading. Initial worker state must appear
within30 seconds; required loading/computing telemetry must appear within30 seconds. Fault pause
expires after30 seconds. Replay/incompatible probes each have180 seconds. Worker resource monitor
also caps600 seconds; external supervisor enforces the earlier arm deadline independently.
Any failure stops the owned process tree and retains partial outputs; logs reach EOF before hashing.
This rehearsal uses the existing SSH foreground supervisor; it does not claim disconnect-independent
multi-hour operation or power-loss recovery. No scheduled tasks/authentication settings are changed.

## Calibration, not long-run permission through this request

Measure job computation time, excluding model loading and explicit boundary monitoring/writes;
GPU results are materialized on CPU before stopping each job timer. Background monitoring and
ordinary host scheduling remain part of observed performance. Discard cycles0–1 for calibration.
Use `ceil(7200 / fastest_cycle_seconds * 1.25)` for a proposed fixed count per long arm. Estimate
both arms' complete payloads plus20% overhead and256 MiB log/journal reserve. If estimate is not
below4 GiB, stop before long-run implementation/execution and report storage infeasibility.
No silent compression/retention/duration change. A later long protocol must be frozen separately,
including two-hour actual active-time minimum, three-hour wall cap, memory-growth tests and
interruption manifest. Passing this rehearsal is not passing the multi-hour engineering gate.

## Prospective correction after rehearsal-01

The first attempt stopped after six committed jobs (12 recorded forwards) with Windows access
error replacing attempt.json. Preserve that failed source identity and outputs. Metadata readers
can hold the destination open briefly on Windows. For rehearsal-02, atomic JSON publication may
retry only PermissionError on Windows for at most one second, in10 ms intervals; the old complete
file remains readable until replacement succeeds. Persistent denial still fails. This does not
retry model calls, change numerical/resource limits, or resume an incompatible old checkpoint.
Verify transient and persistent lock behavior with a weight-free Windows probe before a new
193-attempt run in a separate directory. No scientific or sustained execution is added.
