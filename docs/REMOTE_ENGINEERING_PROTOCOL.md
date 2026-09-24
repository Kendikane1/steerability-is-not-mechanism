# P1-022 — pinned0.6B CUDA engineering protocol

Authority,2026-09-23: user approved preserving/reconciling the remote checkout, transferring the
verified existing0.6B artifacts, the first synthetic CUDA check and progression toward the
previously proposed engineering checks. No1.7B/scientific execution or publishing is included.

## Reconciliation and artifacts

Before updating remote main, copy the eight modified/untracked infrastructure files and binary
patch into private `Research/reports/p1-022-before-reconcile`, verify their hashes, and preserve
Git stash `p1-022 preserved remote infrastructure before reconciliation`. Seven files match the
published701ebd4 baseline exactly; remote AGENTS only lacks the newer runbook paragraph.
Fast-forward main from69d03d7 to published d1ff9bd. Do not reapply obsolete copies over new files.
Do not touch ops, Jupyter credentials, SSH, scheduled-task registration or existing ignored runs.

Deploy a hash-manifested snapshot of reviewed local source/config/tests/docs onto the reconciled
checkout. These remain uncommitted working changes on both hosts; no commit/push is implied.
Transfer only the pinned weight file, seven-file tokenizer bundle and token-reference JSON as
separately authorized artifacts, not through Git. Verify size/SHA before renaming the partial
weight. Preserve the20 GiB Windows disk reserve. No external model download or new model revision.

## Scope and runtime

The model/tokenizer revision, original question, A/B IDs32/33, template, layer13 and float32
numerical/geometry tolerances remain those of the local engineering specification. CUDA is a
new backend baseline, not an assumption of bitwise equivalence with MPS. The0.6B remains purely
synthetic engineering; scientific layer/model choices and pilot/locked guards are unchanged.

Separate `remote_synthetic_cuda_v1` request modes have fixed budgets: single1, no-op6,
coordinate18, resume8 per worker. Existing Mac requests still refuse CUDA. The adapter core
requires explicit CUDA opt-in from the verified CUDA request, strict determinism and IEEE
float32 matrix multiplication. Runtime: native Windows, Python3.12.14, torch2.13.0+cu130,
Transformers5.15.0, tokenizers0.22.2, RTX4060/cuda:0. Eager attention, evaluation/inference,
no cache/generation/autocast/quantization. Seed1729; one intra/inter-op CPU thread.

Set HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1, HF_DEACTIVATE_ASYNC_LOAD=1 and
CUBLAS_WORKSPACE_CONFIG=:4096:8 before CUDA initialization. Use strict deterministic algorithms,
IEEE CUDA matmul/cuDNN precision (TF32 off), cuDNN deterministic=true/benchmark=false.
Verify pinned weights, tokenizer, Transformers source hash, topology, float32 parameter devices
and exact original48 input IDs before forwarding. Do not relax these checks to pass a run.

## Resource and stopping rules chosen before execution

These Windows-specific criteria replace neither the Mac protocol retrospectively nor the future
scientific GPU-memory criterion. Query Windows GlobalMemoryStatusEx and CUDA allocator/device
memory, not macOS pressure/swap APIs. Record loading and forward samples about once per second
and at call boundaries, plus CUDA allocator peak. Samples are not guaranteed total-system peaks.

- At startup: at least4 GiB free GPU,1 GiB available physical RAM and commit capacity.
- During execution: at least1 GiB free GPU,512 MiB available physical RAM and commit capacity;
  memory load less than95%. Always preserve20 GiB free disk.
- Each owned worker has180 seconds after monitor construction and210 seconds external total.
  Telemetry operations taking over5 seconds fail. Resource failure records abort evidence and
  exits the owned worker; supervisor retains partial outputs. No automatic retry/device switch.
- Monitor shutdown must finish within5 seconds. A stuck worker is forcibly terminated by the
  external supervisor; all inherited console writers must reach EOF before checksumming logs.

## Sequential acceptance

1. Single: exactly one scoring pass, finite151936-entry logits, accepted token IDs, correct-minus-
   endorsed log-softmax/logit difference agreement <=1e-12; retain probabilities and raw logits.
2. Mechanics: six no-op/capture/identity passes, then18 axis/dense paired/reverse passes with
   existing P1-007 element1e-5 absolute+relative, margin1e-4 and scaled geometry1e-5 limits.
   Save logits/captures/applied edits; exact equality additionally reported; hooks must clear.
3. Resume: same four fixed jobs/two deterministic shards, uninterrupted reference versus actual
   Windows process-tree termination after INSERT/before COMMIT. Verify that the reported
   worker PID belongs to the launched virtual-environment process before terminating that tree. This is not POSIX SIGKILL. Require
   preserved committed checksum, partial rollback, no duplicates, all saved arrays within limits,
   completed replay0 model loads/forwards, incompatible identity rejected before loading.
   Total17 forward attempts if the complete comparison passes; each worker max8.

No long-run workload is authorized by these small request budgets. After gates pass, predeclare
and verify a separate remote rehearsal/sustained protocol with resource monitoring, immutable
manifest, duration and storage feasibility. Do not change to1.7B or FP16 under this step.
