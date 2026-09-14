# Steerability Is Not Mechanism

Does a lovingness-related activation coordinate that can steer a model also contribute to its
ordinary, naturally elicited sycophancy? The planned experiment estimates the direction from
independent loving-versus-neutral material, measures it before the answer in matched low- and
high-validation-pressure prompts, and replaces only that coordinate with the same item's
natural counterfactual value in both directions.

## Status

**Phase 0: initialization and experimental specification.** This repository currently contains
typed configs, modular interfaces, mathematical primitives, synthetic fixtures, and tests. It
contains no model weights, real pilot/confirmatory data, or scientific results.

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
Its infrastructure tests are complete; model-backed research engineering has not started.

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

Phase 1 starts by resolving the model revision, chat template, first-token convention, and hook
site in `docs/DECISIONS.md`. Model-backed execution is intentionally guarded until those choices
are frozen and the small-model download is explicitly authorized.
