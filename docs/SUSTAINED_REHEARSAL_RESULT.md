# P1-020 — rehearsal stopped during loading

Date:2026-09-23 local (2026-09-22 UTC). **Operational stop; rehearsal not passed.**

## What changed

The user explicitly permitted warning memory pressure for the unattended local engineering
attempt. The new request records that policy. Critical pressure, the256 MiB swap-growth cap,
80% MPS recommended-working-set cap, disk reserves and numerical requirements remain unchanged.
The original P1-019 normal-pressure refusal is preserved as historical evidence.

Implemented a distinct12-cycle rehearsal with a maximum96 forwards per worker, fixed synthetic
jobs in three16-job shards, one model instance per process, repeated-array checks, atomic progress
records, and independent supervisor/worker resource monitors. The designed comparison budget is
193 attempted forwards including an intended midpoint interruption; no long workload is enabled
by this request. Fresh verification passed171 tests, lint/format, type checks and synthetic smoke.

## What actually happened

The supervisor started at17:32:27 UTC. Startup pressure was normal, then became warning, which
was allowed. It stopped the first reference worker while loading the pinned local Qwen weights:

| Observation | Value |
|---|---:|
| Pre-load system swap | 3338.62 MiB |
| Last observed system swap | 3727.94 MiB |
| Observed growth | 389.32 MiB |
| Allowed growth before stopping | less than256 MiB |
| Sampled peak MPS driver allocation | 3,401,973,760 bytes |
| Startup recommended MPS working set | 5,726,633,984 bytes |
| System / worker memory samples | 11 /14 |
| Forward calls / completed jobs | 0 /0 |

The supervisor wrote a cooperative stop request and allowed5 seconds. The worker remained in
model construction, so it was SIGKILLed (exit-9). The supervisor then exited1 and preserved the
failure. Loading did begin, but did not finish; `model_loaded=false` means construction did not
complete, not that no memory was allocated. No answer probabilities or activations were produced.
The observed389 MiB excess reflects discrete sampling; the cap is a stop trigger, not a guarantee
that usage can never overshoot between samples or during termination grace.

## Audit and limits

Checkpoint integrity passed and the result table has zero rows. Source/config hashes match the
verified execution snapshot. The finalized console hash matches, including the delayed Python
resource-tracker cleanup warning after SIGKILL; this exercises the P1-017 log-capture correction.
All artifacts remain local and ignored; no scientific data, remote work or new weights were used.

The stop is evidence that this attempt exceeded its system resource rule. It does not establish
an inherent model-fit failure, a memory leak or that Qwen alone caused the system-wide paging.
MPS sampled driver allocation was below its separate80% stop threshold. We did not relax the
swap cap, retry until success or modify the scientific execution guards.

The rehearsal's forward behavior, intended midpoint recovery, throughput calibration and storage
feasibility remain unmeasured. Therefore no long-run count was frozen and no multi-hour arm was
launched. The long-run runner and its memory-growth audit remain subsequent implementation work.
Phase2 readiness is unchanged. Passing171 unit tests is not a substitute for this runtime evidence.

## Evidence and reproduction

- `outputs/phase1/p1-020/verification-01/verification.json`: all required checks and source hashes.
- `outputs/phase1/p1-020/execution_receipt.json`: exact command, verification hash and exit.
- `outputs/phase1/p1-020/rehearsal-01/report.json`: baseline, frozen identity, stop and worker exit.
- `outputs/phase1/p1-020/rehearsal-01/system.jsonl`: system samples including raw sysctl readings.
- `outputs/phase1/p1-020/rehearsal-01/reference/memory.jsonl`: worker samples including loading.
- `outputs/phase1/p1-020/stop_audit.json`: independent checkpoint, console and source audit.

After addressing competing host memory demand, a deliberate new attempt requires a new output
directory, unchanged limits and fresh verification if code changes:

```sh
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DEACTIVATE_ASYNC_LOAD=1 \
PYTORCH_ENABLE_MPS_FALLBACK=0 uv run --locked --offline python \
  notebooks/check_local_rehearsal.py --output-dir outputs/phase1/rehearsal-retry-01
```

A fresh, idle host session would help distinguish residual host demand from the model-loading
requirement. This is a recommended diagnostic condition, not evidence that it will pass.
