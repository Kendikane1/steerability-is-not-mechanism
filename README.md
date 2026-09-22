# Steerability Is Not Mechanism

Does a lovingness-related activation coordinate that can steer a model also contribute to its
ordinary, naturally elicited sycophancy? The planned experiment estimates the direction from
independent loving-versus-neutral material, measures it before the answer in matched low- and
high-validation-pressure prompts, and replaces only that coordinate with the same item's
natural counterfactual value in both directions.

## Status

**Phase 1: bounded local engineering review complete; broader pre-pilot gates remain open.** Phase 0 initialization
and experimental specification are complete. This repository currently contains
typed configs, modular interfaces, mathematical primitives, synthetic fixtures, and tests. It
contains no real pilot/confirmatory data or scientific results. The pinned Qwen3-0.6B weights
were downloaded with explicit permission and checksum-verified on 2026-09-17 in the ignored
local `models/` directory and are not part of Git. P1-013 verified the 48-token synthetic input
and one full-vocabulary scoring pass in float32. P1-014 verified within-process repeats, capture
and identical-copy replacement with exact equality. P1-015 verified zero-dose and paired/reverse
coordinate replacements for two fixed synthetic directions. This is engineering evidence only;
the consolidated review is in [PHASE1_ENGINEERING_REVIEW.md](docs/PHASE1_ENGINEERING_REVIEW.md).
Multi-hour reliability and safe GPU-memory headroom are still unestablished.

Our stepwise method is in [RESEARCH_WORKFLOW.md](docs/RESEARCH_WORKFLOW.md), with substantive
steps recorded in [RESEARCH_LOG.md](docs/RESEARCH_LOG.md). Downloads remain separately gated.

## Setup and checks

Requires Python 3.12 and [`uv`](https://docs.astral.sh/uv/):

```sh
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
uv run sim-smoke --config configs/local_smoke.yaml
```

The last command is a deterministic synthetic smoke test. It loads no model and writes no
scientific result.

The shared lock selects CUDA-enabled PyTorch on native Windows and preserves the Mac package
source. Use `uv sync --locked` for subsequent reproduction without changing the lock.
For the existing remote PC, see [the operating and recovery guide](docs/REMOTE_COMPUTE.md).
Its infrastructure tests are complete; no remote model-backed research has started.

## Hardware roles

- Apple Silicon M1: Qwen3-0.6B engineering and public reproducibility smoke tests, preferring
  MPS with CPU fallback. It cannot support the scientific claim.
- Remote RTX 4060: candidate Qwen3-1.7B FP16 pilot and primary study, only after pilot decisions
  and gates are frozen.
- Colab/Pro: optional replication capacity; never required by the pipeline.

All long work will use deterministic, resumable manifest shards. Credentials, weights,
datasets, checkpoints, caches, and generated outputs are excluded from Git.

## Layout

- `docs/`: operative research specification, decisions, preregistration draft, and roadmap.
- `configs/`: validated smoke, draft pilot, and guarded locked-experiment configurations.
- `src/steerability_is_not_mechanism/`: reusable schemas, adapters, activation/direction/
  intervention logic, metrics, and manifests.
- `tests/` and `data/synthetic/`: tests and deliberately non-scientific fixtures.

## Next command

Recheck the weight-free baseline at any time with:

```sh
uv run sim-smoke --config configs/local_smoke.yaml
```

Phase 1 measurement choices and remaining runtime checks are recorded in `docs/DECISIONS.md`.
The general model loader and scientific execution paths remain guarded. The separate
`configs/local_single_item.yaml` authorizes only the original synthetic item through its offline
runner. The approved weight download and first scoring check are complete.

The initial local measurement specification is now recorded in
[`configs/local_model_engineering.yaml`](configs/local_model_engineering.yaml), with its
[adapter contract](docs/LOCAL_ENGINEERING_PROTOCOL.md). It pins the P1-005–P1-007 settings
and rejects incomplete or incompatible declarations. This separate specification cannot enable
execution; the command above still runs the original weight-free synthetic smoke test.

The shared adapter core now has synthetic CPU tests for capture, replacement and hook cleanup.
It loads no weights. The separate verified offline Qwen factory passed one scoring check;
the no-op, paired-coordinate and local shard/resume audits also passed. The review preserves a documented historical console-checksum amendment.

To reproduce the one-item engineering check in a fresh process, choose an unused output directory:

```sh
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 \
HF_DEACTIVATE_ASYNC_LOAD=1 uv run --locked --offline python notebooks/run_local_single_item.py \
  --run-dir outputs/phase1/single-item-reproduction-01
```

This requires the verified local tokenizer bundle and weights recorded in the research log.
It performs one forward pass, with no generation or interventions, and refuses to overwrite outputs.


The bounded capture/identity audit uses `configs/local_noop.yaml` and
`notebooks/run_local_noop.py` with the same offline/sequential-loading environment and an unused
output directory. It allows six passes of the original synthetic prompt and stops on a failed
comparison. P1-014 in the research log records results and artifact identities.


The paired-coordinate audit uses `configs/local_coordinate.yaml` and
`notebooks/run_local_coordinate.py` with the same offline/sequential-loading environment.
It permits18 passes on a fixed synthetic pair and checks actual applied-vector geometry.
See the [detailed code and results walkthrough](docs/COORDINATE_ENGINEERING_WALKTHROUGH.md).
These fixtures are not lovingness directions, and this pair did not establish a sycophancy effect.


P1-016 verified four synthetic jobs across two deterministic local shards. An actual process kill
before commit followed by fresh-process resume reproduced all 16 saved arrays exactly, preserved
completed work, and rejected incompatible metadata before model loading. See the
[local resume protocol](docs/LOCAL_RESUME_PROTOCOL.md) for commands, evidence and limits.
Multi-hour, power-loss and remote/scientific execution guarantees remain unverified.


Milestone5 adds a read-only, executable [evidence walkthrough](notebooks/phase1_engineering_review.ipynb).
Its [review](docs/PHASE1_ENGINEERING_REVIEW.md) explains the evidence, two fixes and remaining gates.
It checks saved artifacts without new model inference; it requires the existing ignored local outputs.
