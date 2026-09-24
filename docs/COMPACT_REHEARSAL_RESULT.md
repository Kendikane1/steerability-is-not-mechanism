# P1-026 — Compact rehearsal audit and long-run feasibility

## Outcome

The saved manual-compact-01 rehearsal passes independent audit. Long-run preparation is gated
by the elapsed-time projection, despite the conditional storage estimate fitting the output cap.
No new model inference was performed. No long-run launcher was deployed or run.

| Check | Observed result |
| --- | --- |
| Forward attempts |96 /49 /48 /0 /0 |
| Completed jobs |48 per arm;24 prior committed checksums preserved |
| Across-arm array comparisons |192, all exactly equal |
| Distinct complete payloads |4 per independent arm |
| Catalog bytes |3,739,648 per arm |
| Supervisor-reported output at measurement |8,253,024 bytes (7.87 MiB) |
| Minimum sampled GPU free |4,202,692,608 bytes |
| Peak CUDA allocator allocation |3,162,115,584 bytes |
| Minimum sampled host RAM free |1,186,074,624 bytes |
| Minimum sampled disk free |33,806,770,176 bytes |

Verified archived source hashes, console and checkpoint hashes, worker state, complete IDs,
reference/resume comparisons, geometry, replay/no-load and incompatible-identity rejection.
All342 saved worker samples satisfy the runtime resource limits. Samples are not instantaneous
peak guarantees. The output size is the supervisor's measurement before final report publication,
not an exact byte count of the finalized artifact directory.

## Timing is the remaining feasibility problem

The predeclared fastest-post-warm-up formula yields21,429 cycles per arm (fastest about0.420 s).
The reference's12 cycles contain5.830 seconds of recorded active processing; the observed interval
from model-loaded timestamp through final committed progress is8.015 seconds. The2.185-second
remainder includes monitoring, token checks, validation and writing; it is not all proven to be
storage overhead. Their individual contributions have not been profiled.

Straight extrapolation of8.015/12 seconds per cycle gives14,312.8 seconds (3.98 hours) per arm,
excluding model loading and restart time. The approved cap is10,800 seconds (3 hours) per arm.
This is a short-run estimate including warm-up effects, not a measured long-run duration or proof
that an optimized implementation cannot fit. Nevertheless, it does not support freezing the
current implementation as a feasible overnight protocol. The original plan explicitly requires
checking that active duration, wall cap and storage fit together before execution.

## Conditional storage projection

Estimated1,495,860,840 bytes (1.39 GiB), below4 GiB, assuming byte-identical repeats. Include both
independent catalogs,8 jobs per cycle across two arms, at-most16-job shards, full manifests,
doubled metadata/page allowances and256 MiB journal/log reserve. Measured maximum serialized row
size1719 bytes; shard header753 bytes. Exact formula and assumptions are in feasibility.json.
Every new unique payload must still be retained; this is not a worst-case guarantee.

## Next bounded step

Use existing saved payloads to profile the live writer and monitoring/publication overhead without
model inference. Check repeated checksum scans, transactions, state publication and telemetry
costs individually. Optimize only measured costs while preserving integrity, durable commits,
resource checks and interruption semantics. Test the changed implementation and recalibrate with
a separately scoped short rehearsal if the execution path changes. Do not lower the active-time
minimum, increase the wall cap, omit retained arrays or append jobs after seeing long-run outcomes.
A disconnect-independent long launcher remains pending until a feasible protocol is established.

## Evidence

Local artifacts: `outputs/phase1/p1-026/`, including `retrieved/`, `audit-final/audit.json`,
`legacy-audit/audit.json` and `feasibility.json`. The audit client supports original and compact
layouts; both saved runs passed after the client change. Model-backed evidence remains the
user-run short rehearsal, not fresh inference during this audit.

Archive SHA256: `b38834aea36c3d5ae6dc70ec991b4974dc7761b0c4bf620183845567a15af045`.
Original report SHA256: `63fc19e9478e1319245e98837ad502cfad0f7badfd0c2f454d768a8fc4463d2e`.
