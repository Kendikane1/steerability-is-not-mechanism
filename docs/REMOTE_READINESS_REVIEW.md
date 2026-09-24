# P1-021 — read-only remote readiness

Observed2026-09-23,02:37–02:39 UTC. **Suitable for preparing a bounded CUDA engineering test;
model fit and reproducibility remain untested.**

## Fresh observations

| Check | Observation |
|---|---|
| SSH | Successful with existing identity, public-key-only authentication and strict host-key checking |
| GPU | NVIDIA GeForce RTX4060,8188 MiB total,7891 MiB free,0% utilization,36°C |
| Driver | 591.86 |
| PyTorch | 2.13.0+cu130; CUDA build13.0; CUDA available; one device |
| Host RAM | 7.90 GiB total,4.83 GiB free |
| C: disk | 31.36 GiB free; about11.36 GiB above the runbook's20 GiB reserve |
| Python | 3.12.14, versus the Mac's previously recorded3.12.13 |
| Other packages | Transformers5.15.0, tokenizers0.22.2, NumPy2.5.2, safetensors0.8.0, accelerate1.14.0 |
| Scheduled tasks | Jupyter, KernelCheck, PythonJob and SyntheticProgress all Ready (not Running) |
| Expected pinned0.6B model file | Absent at the project's expected revision path; other caches were not searched |

These are point-in-time availability readings, not a reserved allocation. GPU memory free and
used values need not sum to total because the driver can reserve memory. CUDA availability was
queried without creating tensors, loading a model or starting a task. No environment installation,
code deployment, weight transfer, model download, Jupyter launch or scientific run was performed.

## Checkout reconciliation is needed

Remote `main` remains at `69d03d76c35dec737544dd1f5a78ba88203601ae`, with five modified files:
AGENTS, README, DECISIONS, pyproject and lock; plus untracked PROJECT_STANDARD snapshot,
REMOTE_COMPUTE runbook and environment test. This is the preserved earlier infrastructure work.

The remote lockfile and pyproject are byte-identical to the Mac's current versions. The runbook,
standard snapshot and environment test also match. Other instruction/planning files differ.
Do not pull/reset over this dirty checkout or infer that local uncommitted engineering files
are already on GitHub. Preserve a private backup of the remote patch and untracked files before
any separately authorized reconciliation. An isolated reviewed checkout is an alternative.

Remote parent instruction files are absent; its project instructions specify the bundled standard
fallback. Its snapshot hash matches the standard already read locally. No instruction files were
changed remotely.

## Recommended next bounded step — proposal only

1. Preserve and review remote changes, then establish a checkout of the reviewed engineering
   implementation. Do not copy a Mac virtual environment. Existing package parity makes a broad
   reinstall unnecessary unless subsequent checks expose a concrete problem.
2. Scope an explicit remote0.6B **engineering-only** exception to the current local-only wording.
   Add a separate CUDA runner; the existing Mac runner stays MPS/CPU. Its exact-package guard
   also needs a separately reviewed CUDA-wheel expectation, not a blanket relaxation.
3. Transfer the already verified1,503,300,328-byte0.6B weight file and pinned tokenizer bundle
   from Mac to Windows, with matching checksums, rather than assuming a remote cache or fetching
   a new model. This transfer is proposed, not performed or authorized by the readiness check.
4. Freeze the first run: one original synthetic question, same model/tokenizer revision, same
   48 input IDs, bare A/B, float32, eager attention, no cache/generation, one forward maximum.
   Specify CUDA determinism/TF32 settings, load/score deadline and GPU/system-RAM/disk stop rules
   before execution. Monitor Windows host RAM as well as VRAM: it still has only8 GiB RAM.
5. Accept only verified artifact/runtime identity, finite full-vocabulary scores and agreement
   among the score arithmetic cross-checks. Record GPU memory/time observations. This is a new
   CUDA baseline; do not assume bitwise agreement with MPS or reuse local tolerances as a
   validated cross-device guarantee. Capture/intervention/resume follow as separate checks.

This keeps the initial platform move separate from the later1.7B FP16 scientific-candidate
assessment. No pilot/locked choices or execution permissions are implied.

## Evidence

Raw read-only scripts, outputs and exit metadata are in ignored
`outputs/phase1/p1-021/readiness-01/`. Main metadata JSON SHA-256:
`7fd02aa76e549e86f2e8af23624316986cb4722e76bba9a8f24a595db33471c5`.
Concise follow-up JSON SHA-256:
`ebca6963354a68e66c5386fd5cc4e6a581bec405b9d9ca596e042923d9baa38c`.
Connection/account/key details are deliberately omitted from tracked records.
