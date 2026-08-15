# Project instructions

Read the parent `../PROJECT_STANDARD.md` and this file completely before work. The parent
standard governs environment, layout, reproducibility, and verification; this file governs
scientific scope. If they conflict within this repository, preserve the stricter scientific
constraint here.

## Scientific objective

Test whether an independently estimated lovingness-related activation direction makes a
site-specific causal contribution to naturally elicited sycophancy in one model and objective
task regime.

## Non-negotiable constraints

- Construct the lovingness direction only from independent loving-versus-neutral material,
  never from sycophancy labels.
- Keep direction extraction, direction validation, development items, and locked test items
  separate. Keep item families and paraphrases in one split.
- Use objective binary factual or reasoning decisions.
- The primary outcome is correct-option minus user-endorsed-option log probability at the
  first generated decision token.
- Measure and intervene at a frozen pre-answer activation position.
- The main intervention must replace the direction coordinate using the same item's naturally
  observed pressured-versus-low-pressure difference, never an arbitrarily amplified dose.
- Include reverse replacement and matched random, shuffled-donor, sign-reversed, capability,
  correct-user, and third-party controls.
- Do not inspect locked-test results until prompts, exact model/tokenizer revisions, layer,
  direction, analysis, exclusions, and controls are frozen and recorded.
- Do not add fine-tuning, RL, DPO, sparse autoencoders, natural-language autoencoders, or an
  LLM judge as the primary evaluator.
- Do not describe an activation direction as evidence that the model experiences emotion.
- The strongest permitted claim is a site-specific causal contribution in one model and task
  regime—not global necessity, uniqueness, or an exact mediated fraction.

## Execution constraints

- Qwen3-0.6B is for local engineering/reproducibility smoke tests only. Local device order is
  MPS when supported, then CPU; never assume local CUDA.
- Qwen3-1.7B FP16 on the remote RTX 4060 is only a candidate primary model and requires the
  scientific pilot to pass. Colab is optional replication capacity, never a core dependency.
- Do not download weights, access remote compute, create confirmatory data, or run scientific
  experiments during Phase 0.
- Long jobs must be deterministic, resumable, manifest-driven, and split into independently
  verifiable shards. Never store secrets in Git.
- Synthetic fixtures may test engineering. They must be visibly marked synthetic and can never
  enter a scientific estimate.

## Required workflow

Before pilot or locked execution, resolve the applicable items in `docs/DECISIONS.md`. Locked
execution additionally requires a frozen preregistration, immutable manifest hashes, a clean
verification run, and an explicit human action changing the locked config from draft to
executable. Never weaken a guard merely to make a run proceed.

