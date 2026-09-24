# P1-022 — Short CUDA engineering checks

**Result: passed.** Pinned Qwen3-0.6B float32 on the Windows RTX 4060 completed the
single-score, activation-edit and short interruption/resume checks. These are synthetic
engineering results, not evidence about lovingness or scientific-model readiness.

## Evidence

| Check | Observed result |
| --- | --- |
| Single score | A probability0.9097237795; B0.0888458088; correct-minus-endorsed margin2.3262386322 |
| Capture / no-op | Six passes accepted; unchanged scores matched exactly |
| Coordinate replacement |18 passes accepted, including both directions and both synthetic direction fixtures |
| Geometry | Axis errors zero; dense maximum projection error1.12e-7, orthogonal error1.24e-6, below the frozen scaled limits |
| Interrupted versus uninterrupted | Four unique jobs,16 saved arrays, all exactly equal |
| Recovery safeguards | Committed row preserved/skipped; partial transaction recomputed; completed replay zero work; incompatible identity refused before loading |
| Resources | Lowest sampled free GPU approximately3.91 GiB; CUDA allocator peak approximately2.945 GiB across these short runs |
| Verification |185 weight-free tests passed on Mac and Windows; local lint/format and source/test/runner type checks passed |

There were42 model-forward attempts:1 single,24 mechanics,17 resume including deliberately
interrupted work. The Windows process-tree shutdown was also checked without loading weights.
The scientific model, layer, direction and pilot choices remain open.

## What changed

A separate CUDA request and runtime preserve the Mac runners' scopes. They verify existing
pinned artifacts, use deterministic float32 computation, monitor Windows RAM/GPU/disk reserves,
and enforce small call/time budgets. The supervisor checks worker ownership before terminating
the Windows virtual-environment launcher and its actual Python child.

Remote infrastructure edits were backed up with hashes and retained in a Git stash before
fast-forwarding to the published checkpoint. Reviewed source was transferred with a file manifest.
No infrastructure authentication settings changed; no new model was downloaded. Local and remote
working changes remain uncommitted. No commit or push was performed.

## Artifacts and limitations

Raw evidence lives under ignored `outputs/phase1/p1-022/` on Windows. The local
`final-audit.json` records82 file hashes, all console/array/checkpoint validations and independent
SQLite/full-array comparisons. Stage report hashes are recorded in the research log.
A transient connection failure interrupted individual-file retrieval; the successful remote
checks were preserved and audited after reconnecting. The complete archive was then retrieved
and all82 evidence files verified locally under `verified-evidence/`. Partial downloads are not
authoritative.

These checks are short. They do not establish multi-hour reliability, guaranteed instantaneous
memory peaks, power-loss durability, or Qwen3-1.7B FP16 capacity. Next is a separately scoped
12-cycle CUDA rehearsal, then storage/duration feasibility before any multi-hour workload.
