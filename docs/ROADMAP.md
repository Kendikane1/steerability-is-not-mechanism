# Phase roadmap

Status, 2026-09-22: Phase 1 milestones 1–2 have local engineering evidence: pinned input/runtime
specification and one verified synthetic Qwen scoring pass on MPS (P1-013). Follow
`RESEARCH_WORKFLOW.md` and `RESEARCH_LOG.md`. Milestone3 capture/identity and within-process
repeatability passed for one prompt/site (P1-014); zero-dose and paired/reverse geometry passed
for two synthetic directions (P1-015). Milestone4 short local shard/SIGKILL/resume checks passed
with exact cross-process array equality (P1-016). Milestone5 consolidated review is complete
(P1-017; `PHASE1_ENGINEERING_REVIEW.md`),
with an explicit historical console-checksum amendment and fresh verification.
The broader Phase1 exit gate is not yet met: multi-hour reliability, safe memory headroom and
scientific choices remain open. Next: specify a sustained local synthetic engineering check.
No scientific execution has begun.

| Phase | Scope | Exit condition |
|---|---|---|
| 0 — initialization | Specifications, typed configs, modular skeleton, synthetic fixtures/tests. No weights or scientific data. | Full local verification and synthetic smoke pass. |
| 1 — engineering smoke | Freeze 0.6B revision/token protocol; implement adapter/hooks; test deterministic capture, replacement, sharding, and resume locally. | Engineering gate passes; no scientific inference. |
| 2 — two-week scientific pilot | Build independent pilot-only direction material and 20 objective items; verify the phenotype and gates on scientifically relevant compute. | Predeclared go/no-go or documented pivot; pilot never enters final estimate. |
| 3 — development | Audit/freeze direction sets and objective generator; screen neutral items; select one layer and intervention/control rules using development only. | All scientific/analytic decisions resolved without locked-test inspection. |
| 4 — freeze/preregister | Finalize hypotheses, exclusions, splits, statistics, controls, exact revisions and hashes; create immutable locked manifest. | Preregistration frozen and explicit execution acknowledgement recorded. |
| 5 — locked execution | Run all main conditions and controls in deterministic resumable shards without partial-result inspection; then execute frozen analysis. | Immutable result bundle, intervals, diagnostics, deviations, and bounded conclusion. |

Colab replication or a second model family begins only after the one-model core is complete and
cannot alter the locked primary analysis.
