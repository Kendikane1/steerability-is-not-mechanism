# P1-027 — Fixed remote synthetic endurance protocol

User approved an overnight duration revision on2026-09-25. The previous3-hour arm limit
is superseded prospectively by6 hours per arm, including loading and planned recovery;
up to12 hours total plus bounded final audit. Skip further optimization/model rehearsals.
Retain essential automated guards: RAM/commit, GPU, disk/output, liveness, numerical integrity,
owned-process termination and durable checkpoints. Automated monitoring runs locally on Windows.

Frozen workload:21,429 cycles per arm,85,716 jobs,5,358 at-most16-job shards,171,432 forward
calls per full arm. Fixed midpoint index42,858 is a capture job:85,717 attempted calls before
termination and85,716 after restart. Total342,865 attempts across two arms. Replay and changed-
identity probes perform zero model loads/forwards. Require at least7,200 seconds actual active
processing per arm, excluding load, monitoring, writes and pauses. No automatic extra cycles.

Use the exact pinned0.6B float32 CUDA synthetic fixtures, block13, seed1729, no generation,
no KV cache and unchanged numerical/geometry checks. Separate sustained request leaves the
96-call rehearsal and scientific guards unchanged. Full immutable manifest stored once as
JSONL and bound by hash, alongside source/config/lock/runtime identity. Stream16 jobs at a time;
state stores counts rather than growing ID lists. Each arm retains its own lossless catalog.

Reference runs uninterrupted; comparison pauses after INSERT/before COMMIT at the fixed midpoint.
Supervisor verifies the owned worker and committed-prefix digest, then terminates its process tree.
Allow300 seconds for deliberate prefix inspection/termination (not active processing); otherwise
retain180-second progress,30-second startup/telemetry and5-second telemetry freshness limits.
Resume skips exactly42,858 jobs with unchanged prefix; loading begins only at unfinished work.
Completed replay and incompatible identity probes each have a1-hour wall cap for streamed audit.
No automatic retry after any unexpected failure. Keep source frozen throughout the run.

Keep startup4 GiB/runtime1 GiB free GPU; startup1 GiB/runtime512 MiB free physical RAM and commit;
memory load below95%;20 GiB free disk;4 GiB total outputs. Conditional storage budget remains
below4 GiB with1 GiB reserved for telemetry/logs/journals instead of256 MiB. Unique payloads are
never discarded. Worker and supervisor enforce time/resource checks; final audit streams shards.
Do not call the small48-row snapshot on the long run. Checksums are hashed incrementally.

Memory-growth acceptance: exclude first10 minutes after each load; compare median CUDA reserved
allocation and worker RSS during minutes10–20 with the final10-minute window. Growth above
max(256 MiB,10% baseline) fails acceptance. Retain one sample per monotonic second for these
windows; bound in-memory windows to600 seconds. Missing/insufficient windows fail; sampled
memory is not an instantaneous-peak guarantee. Do not clear allocator caches to pass.

Execution remains manual after necessary weight-free implementation verification. A foreground
launcher requires the SSH connection and Mac awake. Any disconnect-independent wrapper must be
verified separately before being advertised as safe to disconnect. Passing this endurance run
would support only this0.6B synthetic configuration, not future models or scientific validity.

Frozen JSONL manifest:19,384,222 bytes; SHA256
`c00f8116f3f451e5754c3d4c24aeb76535ac5d3faf4147183e96895681bda382`.
Verify this before configuring/loading the model. The packaged `psutil` already required by
locked Accelerate supplies worker RSS; record its installed version in identity. At least590
one-second samples in each600-second memory window are required; log those raw RSS/reserved
samples for independent review. No dependency or lockfile change is needed.

Use existing Limited/S4U `PythonJob` slot, only when Ready. Preserve its previous manifest,
then point it at the reviewed Python entry. Do not register new tasks or change authentication.
Verify the same scheduled entry in a15-second no-model probe across SSH disconnection before
manual Start. The entry verifies source hashes and holds the shared exclusive launcher lock.
Manual Stop writes a stop request consumed by the supervisor; do not stop only the outer task
and leave its child workers running. Windows must stay powered and awake. No automatic boot
restart or unattended retry is promised. Extra replay/final-audit stages can add up to2 hours
beyond the two6-hour arm caps; expected compute run remains roughly8 hours plus review work.
