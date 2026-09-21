# Steerability Is Not Mechanism

Does a lovingness-related activation coordinate that can steer a model also contribute to its
ordinary, naturally elicited sycophancy? The planned experiment estimates the direction from
independent loving-versus-neutral material, measures it before the answer in matched low- and
high-validation-pressure prompts, and replaces only that coordinate with the same item's
natural counterfactual value in both directions.

## Status

**Phase 1: first synthetic Qwen scoring pass completed on local MPS.** Phase 0 initialization
and experimental specification are complete. This repository currently contains
typed configs, modular interfaces, mathematical primitives, synthetic fixtures, and tests. It
contains no real pilot/confirmatory data or scientific results. The pinned Qwen3-0.6B weights
were downloaded with explicit permission and checksum-verified on 2026-09-17 in the ignored
local `models/` directory and are not part of Git. P1-013 verified the 48-token synthetic input
and one full-vocabulary scoring pass in float32. Capture/replacement and repeatability on Qwen
remain unverified. This is engineering evidence only.

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
model-backed activation capture, replacement and repeatability are the next bounded step.

To reproduce the one-item engineering check in a fresh process, choose an unused output directory:

```sh
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 \
HF_DEACTIVATE_ASYNC_LOAD=1 uv run --locked --offline python notebooks/run_local_single_item.py \
  --run-dir outputs/phase1/single-item-reproduction-01
```

This requires the verified local tokenizer bundle and weights recorded in the research log.
It performs one forward pass, with no generation or interventions, and refuses to overwrite outputs.
