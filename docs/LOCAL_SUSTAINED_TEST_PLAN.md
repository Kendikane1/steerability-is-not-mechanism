# Proposed sustained local engineering test — P1-018

Status: **limits approved; implementation/execution authorized conditionally on the gates;
not a completed gate**. Date: 2026-09-23.
Baseline: milestone 4–5 checkpoint `d1ff9bd`. No model calls were made to prepare this plan.

## Question and prediction

Can the existing local synthetic capture/replacement workload run for multiple hours without
numerical drift, growing memory use or loss of completed work after interruption?

Prediction: repeated outputs remain within the existing tolerances, memory reaches a stable
range after warm-up, and resumed results match an uninterrupted reference. A mismatch, steadily
increasing memory, incomplete monitoring or a resource stop prevents a pass. None is evidence
for or against a lovingness mechanism.

## Recommended sequence

1. Implement and unit-test a separately scoped sustained runner and resource monitor. Preserve
   every existing runner's budget and all scientific/download guards. Do not increase the
   eight-forward P1-016 request or put it in an unrestricted retry loop.
2. Run a bounded rehearsal: 12 cycles of the four existing synthetic jobs (96 forwards maximum),
   one model instance, maximum 10 minutes including loading. Include a separately recorded
   interruption/restart check of the new runner. Predeclare its complete call budget before use.
3. Use rehearsal throughput and output sizes only to propose the long-run count and storage
   estimate. Freeze the full manifest, count, per-shard layout, interruption ID, monitoring
   implementation, resource limits and hashes before the long run. No outcome-dependent selection.
4. Run an uninterrupted reference and an interrupted/resumed comparison sequentially, each
   targeting at least two hours of active job processing. This means roughly four or more hours
   total, not a two-hour combined test. Do not start either until the reviewed protocol is frozen.
5. Compare all completed results and operational records, then review what remains before Phase 2.

The immediate next implementation step is the runner/monitor and its weight-free tests. The
user subsequently approved proceeding through rehearsal and long execution if the limits pass.
P1-019 startup preflight refused warning-level system memory pressure before any model load.
The full runner/monitor and model-backed rehearsal remain incomplete; see the research log.

## Fixed workload and duration

Reuse the same P1-015 prompt pair, block13, bare-A/B scoring, float32 precision, pinned local
Qwen3-0.6B revision and offline runtime settings. Prefer MPS; CPU would be a separate run with
separate throughput calibration and could not establish MPS headroom. No new questions,
scientific direction, layer selection, generation or training.

A cycle contains high capture, low capture, high paired edit and reverse low paired edit. These
are the existing four self-contained jobs: eight forwards per cycle. Retain the fixed dense
synthetic direction and the same per-fixture seed across repetitions. Give each repetition an
immutable unique job ID; it is a technical repeat, not another scientific item.

Keep one model loaded across sequential shards in each process. Reload only after intentional
interruption or a separately recorded failure. Repeated model teardown would conceal some
within-process accumulation. Do not clear allocator caches between jobs to manufacture stability.

Choose the number of cycles from the rehearsal's fastest complete post-warm-up cycle, with a
proposed 25% duration margin: `ceil(7200 seconds / fastest_cycle_seconds * 1.25)`. Freeze that
count before running. The formula estimates duration; it cannot guarantee two hours. Measure
actual job-processing time, excluding model loading, deliberate pauses, sleep, recovery downtime
and monitoring-only waits. If an arm finishes under two hours, report insufficient duration;
do not silently append jobs. Proposed wall-clock cap is three hours per arm, including recovery.
If rehearsal estimates cannot fit the duration, storage and wall limits together, revise the
plan explicitly before execution.

## Shards, interruption and comparisons

A manifest is the complete ordered list of jobs and their settings, hashed before execution.
Use deterministic sequential chunks of at most16 jobs per shard, separate from P1-016's existing
hash assignment. This bounds each shard's payload to32 MiB under the unchanged2 MiB/job limit,
leaving space below the64 MiB database cap. Assert actual sizes; estimates are not guarantees.

Run both arms against the same manifest in different new output directories. Select the first
job after the manifest midpoint as the interruption target before starting. In the comparison
arm, pause after INSERT/before COMMIT, record already committed hashes and the rollback journal,
then SIGKILL only the owned worker. Resume in a fresh process with exactly the same identity.
If failure or a timeout occurs before the selected boundary, preserve it; do not substitute a
more convenient target or retry automatically. The proposed single interruption exercises both
long-lived execution and fresh-process recovery, not power loss.

Require every expected ID exactly once in the final database union; committed jobs skipped
unchanged; unfinished work recomputed; completed replay performs zero model loads/forwards;
incompatible identity rejected before loading. Drain descendant output to EOF before hashing.

Compare every saved array between arms and each repetition against its corresponding first
reference-cycle fixture. Preserve full logits/activation/edit arrays and report exact equality
as well as errors. Require finite arrays, identical shapes/dtypes, element error
`<= 1e-5 + 1e-5 * abs(reference)` and A/B margin error `<= 1e-4`. Retain P1-007 coordinate geometry
limits, exact preservation of unedited positions and hook cleanup. No tolerance relaxation.
Reusing first-cycle fixtures checks repeatability, not the scientific validity of the task.

## Proposed resource limits and measurements

These conservative limits were approved by the user; they are not measured capacity or hardware guarantees. Confirm the
monitor's units, sampling overhead and failure behavior in the rehearsal before freezing them.

| Measure | Proposed rule | Reason |
|---|---|---|
| MPS driver allocation | Stop at or above80% of the startup recommended working-set size | Reserve20% relative to the runtime recommendation; this is not free system RAM |
| OS memory pressure | Require normal at start; stop on warning/critical | The M1 shares memory between CPU, GPU and other applications |
| System swap usage | Stop if usage grows by256 MiB over pre-load baseline | Avoid treating heavy paging as healthy fit; record possible other-app contributions |
| Post-warm-up memory growth | Final10-minute median driver allocation or resident process memory exceeds first post-warm-up10-minute median by more than max(256 MiB,10% of that baseline): no pass | Detect persistent accumulation while allowing bounded caching; exclude a fixed first10 minutes after each model load |
| Disk space | Require10 GiB free at start; stop below5 GiB or at4 GiB total new output | Leave room for journals, both arms, logs and failed attempts |
| Liveness | Stop on no completed job for180 seconds, except the separately timed deliberate pause/reload | A hung worker must not become a silent overnight job |
| Monitoring | Stop if required readings are unavailable or stale for more than5 seconds | Missing telemetry cannot establish headroom |

Collect time-stamped MPS tensor allocation and driver allocation inside the worker at load,
forward and job boundaries. Sample driver allocation and resident process memory at a proposed
one-second interval, and OS pressure/swap/disk at a proposed five-second interval. Validate
thread/API behavior and sampling overhead before adopting that monitor. Record monotonic time
as well as UTC, actual sample gaps, loading peaks, per-forward timing and completed-job counts.
A separate supervisor must enforce wall/liveness limits even if the worker stops responding.

Installed PyTorch's `torch/mps/__init__.py` documents the distinction: tensor allocation excludes
allocator caches; driver allocation includes caches and framework allocations; recommended
maximum is Metal's recommended working set. Do not add process resident memory and MPS memory
as though they were disjoint pools. OS memory pressure/swap are system-wide and may reflect other
applications. Pause unrelated heavy work for the test and record competing workload changes.

Periodic readings provide **sampled maxima**, not a guaranteed instantaneous peak. Record that
limitation explicitly. Stable samples plus unused recommended capacity and normal OS pressure
would support bounded local headroom; they cannot prove the remote1.7B FP16 workload fits or
alone close its GPU-memory gate. Any stronger peak claim needs a validated measurement method.

On a resource limit, preserve completed work and record a stopped/failed attempt. Request a
cooperative stop between jobs; terminate only the owned worker if it does not stop promptly.
Never lower precision, enable implicit fallback, change identity or loosen a limit to finish.
Freeze the exact grace/deadline and OS-monitor commands with their parser tests before execution.

## Evidence, unresolved details and interpretation

Before execution, freeze the runner/request schema, numerical protocol, model/tokenizer hashes,
full manifest and shard hashes, source/lock hashes, resolved device, seeds, limits, monitoring
API/OS command definitions and exact interruption/restart budget. Keep output directories unique.
Require a fresh clean verification run of the implementation. Long-run storage feasibility must
be checked using the rehearsal's measured bytes per cycle for both arms, plus journal/log reserve.
The current checkpoint is not an executable sustained-run configuration.

Open implementation details: supported macOS pressure/RSS/swap readings and parsers, monitoring
thread behavior, startup/recovery deadlines, exact rehearsal fault-injection budget, cycle count,
shard count and final disk estimate. Do not fill these with invented measurements. Record any
revision before its affected execution; a failed attempt remains evidence.

A pass would establish sustained local synthetic execution and measured resource behavior under
this exact workload. It would not establish remote scientific-model readiness, a sycophancy
phenotype or an independently validated lovingness direction. Phase 2 still requires separate
scientific-compute checks, frozen pilot decisions and authorized scientific execution.


## P1-019 startup implementation and source semantics

`notebooks/check_sustained_resources.py` runs the weight-free startup system gate and saves
raw readings, timestamps, source hashes and its refusal/pass status. It is not the sustained
runner and does not establish model headroom. Use a new output directory for each attempt:

```sh
uv run --locked --offline python notebooks/check_sustained_resources.py \
  --output-dir outputs/phase1/p1-019/preflight-next
```

Read-only `sysctl -n kern.memorystatus_vm_pressure_level` returns dispatch constants:1 normal,
2 warning,4 critical. Apple's [conversion implementation](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_memorystatus_notify.c)
and [constant definitions](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/event_private.h)
confirm this; do not confuse them with internal pressure enums. Unknown values fail closed.
`sysctl -n vm.swapusage` is parsed strictly in MiB; unsupported format/units and command timeouts
are errors. Each command has a2-second timeout, with a5-second total reading-age gate.
Disk availability comes from the output filesystem via Python's `shutil.disk_usage`.
This sysctl is platform-specific; its availability is checked at runtime rather than assumed.

## P1-020 explicit user revision and frozen rehearsal details

On2026-09-23 the user explicitly requested continuation despite warning pressure while the
laptop is unattended. **For this new rehearsal only, warning pressure is recorded rather than
an automatic refusal. Critical/unknown pressure still stops.** This supersedes the normal-only
pressure row for P1-020; P1-019 refusal remains valid under its original protocol. A completion
under warnings cannot satisfy the original normal-pressure headroom criterion. All disk, swap,
MPS allocation, telemetry and numerical limits remain unchanged; no scientific guard changes.

The separate `local_rehearsal.yaml` permits exactly12 cycles/48 jobs/96 forwards per complete
arm, three sequential shards of16 jobs. The reference arm has96 calls. The interrupted arm
attempts49 calls before the midpoint capture is killed, then48 on resume:97 total including one
discarded capture,193 combined across both arms. Replay and incompatible identity probes allow
zero model calls. No worker exceeds96. An unexpected failure stops the sequence without retry.

One model remains loaded across all three shards. Repeated fixtures use seed1729, immutable
cycle-qualified IDs and the existing four independent jobs; sorted fixture order matches P1-016.
No-op and coordinate geometry protocols are unchanged. Compare every saved array against its
first-cycle fixture and against the other arm. The fault target is manifest index24 after its
INSERT/before COMMIT. Require the preceding24 IDs committed and hashed unchanged after recovery.

The supervisor monitors OS pressure, swap and output-filesystem capacity about once per second
(more frequent than the proposed five-second maximum). Worker thread samples MPS allocation and
RSS about once per second and at load/forward/job boundaries. RSS uses read-only
`/bin/ps -o rss= -p <owned-worker-pid>`, KiB converted to bytes; nonnumeric readings fail. Actual
sampling intervals and overhead are recorded; no instantaneous-peak guarantee follows.

Startup report deadline30 seconds; no committed-job progress deadline180 seconds, including
initial model load. Each arm has600 seconds including reload/recovery; fault pause self-expires
at30 seconds. Supervisor issues a stop file on resource failure, allows5 seconds for cooperative
exit, then SIGKILLs only its owned worker. Missing/stale memory telemetry after startup or an
explicit sampler error also stops. Logs are finalized only after inherited output pipes reach EOF.
Swap baseline is fixed before the reference arm and retained through resume, not reset to hide
paging growth. Model construction is lazy so completed replay and incompatible identity probes
remain zero-load checks. Source/lock/request/plan/environment identities are checkpoint-bound.

For rehearsal throughput only, discard the first two cycles as warm-up and use the fastest of
cycles2–11 in the predeclared count formula. This is distinct from the10-minute long-run memory
warm-up. Estimate two-arm retained payload bytes with20% overhead plus256 MiB journal/log reserve;
if this exceeds4 GiB, no long run is feasible under this storage plan. Long execution remains
unimplemented/unfrozen until the rehearsal and feasibility check pass. Never run a four-hour
workload through the96-call rehearsal request.
