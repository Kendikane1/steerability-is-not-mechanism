# Decision log

## Settled by the kickoff brief

- Phase 0 creates specifications and synthetic engineering tests only.
- Direction data are independent of sycophancy data and labels; extraction, validation,
  development, pilot, and locked-test partitions do not overlap.
- Decisions are objective and binary. The primary score is the correct-minus-user-endorsed
  first-token log-probability margin.
- Activation capture and intervention happen before the answer.
- The primary edit is the same item's natural coordinate difference and includes the reverse.
- Required controls: matched random, shuffled donor, sign reversal, capability/no assertion,
  correct user, and third party.
- Local engineering uses Qwen3-0.6B with MPS/CPU; the conditional primary is Qwen3-1.7B FP16 on
  an RTX 4060; Colab is optional only.
- No training, RL/DPO, SAE/NLA, primary LLM judge, anthropomorphic claim, global mechanism
  claim, uniqueness claim, or exact mediated fraction.
- Long work is resumable, deterministic, sharded, and secret-free.

## Open before Phase 1 engineering

### Infrastructure decisions recorded 2026-09-14

- Native Windows is the current remote environment; no WSL, Docker, or full CUDA toolkit is
  required by the installed setup. This is infrastructure, not selection of a scientific model.
- Adopt the Windows agent's platform-marked CUDA PyTorch source and exact lockfile, retaining
  the Mac source and original public release versions. Use Python 3.12 and locked sync.
- Jupyter remains authenticated and loopback-only, reached through the existing SSH tunnel.
  On-demand Limited/S4U scheduled tasks provide process independence from the launch terminal.
- A standalone clone uses the bundled parent-standard snapshot if its parent file is absent.
- See `REMOTE_COMPUTE.md` for evidence and limits. GPU arithmetic and connectivity do not
  establish FP16 model headroom, deterministic model hooks, or scientific-job resume.
- Full clean-machine infrastructure recreation, private backup, Tailscale expiry/recovery,
  Windows update/power scheduling, and storage expansion remain operational follow-ups.

### Engineering choices still open

- Exact Qwen3-0.6B model and tokenizer revisions, license record, chat template, non-thinking
  setting, dtype on MPS/CPU, and deterministic-kernel tolerance.
- Exact first-decision token representation (`A`/`B`, whitespace behavior, and proof that each
  scored option has an unambiguous tokenizer treatment).
- Exact residual-stream hook convention (block input/output and pre/post normalization), final
  assistant-delimiter position, and layer-number indexing.
- Model-adapter contract for activation replacement during a single next-token forward pass.
- Phase 1 shard size, checkpoint format, resume semantics, activation tolerance, and storage
  budget.

## Must resolve before the scientific pilot

- Exact Qwen3-1.7B model/tokenizer revisions and confirmed remote 4060 type, VRAM, FP16 support,
  uptime, transfer reliability, and memory-headroom criterion.
- Pilot objective domains, item-family definition, prompt templates, response suffix, neutral
  screening rule, balanced answer order, and allowed exclusions.
- Loving/neutral construct rubric; extraction/validation family sources and counts; direction
  estimator, normalization, sign convention, validation bootstrap, positive-valence/arousal
  controls, and 70% threshold interpretation.
- Candidate-layer fractions mapped to exact indices and the development-only selection rule.
- Precise definitions of 0.30 SD pressure effect, 75% neutral accuracy, 90% validity, five-point
  capability loss, and the single allowed prompt revision/48-hour diagnostic.
- Whether the pilot occurs first on 0.6B, 1.7B, or both. The kickoff permits 0.6B only as
  engineering evidence, so a scientific go/no-go claim cannot rest on it alone.

## Must resolve before development freeze / preregistration

- Final extraction, validation, pilot, development, and locked sample sizes with power/simulation
  rationale; complete item generator, domains, family grouping, hashes, and split seed.
- Exact high/low, correct-user, third-party, and no-assertion wording and whether prompt-family
  variants are repeated measures or one assigned form per item.
- One primary layer/site/direction; nuisance overlap threshold; covariance-matched random-vector
  algorithm; shuffled-donor derangement; equal-norm sign-reversal semantics.
- Bootstrap resampling unit and repetitions, one-/two-sided intervals, alpha/coverage,
  mixed-effects formula, secondary-analysis multiplicity correction, and missingness handling.
- Treatment of ties, refusals, tokenizer ambiguity, invalid outputs, numerical failures, reruns,
  and incomplete shards.
- Objective coherence/fluency rule, entropy threshold, capability suite, and acceptable edit norm.
- Exact freeze artifact, code/config/model/data hashes, blinding procedure, test-result access
  control, deviation policy, and rule for releasing the locked execution guard.

## Rejected or deliberately out of scope

- Appendix A, “Persona Without the Costume,” and its style-versus-policy factorial study.
- Fine-tuning, RL, DPO, SAEs, NLAs, broad emotion taxonomies, harmful task material, and a primary
  LLM judge.
- Arbitrarily large steering as confirmatory evidence, quantized primary activation geometry,
  model-family sweeps before the core result, or Colab as required infrastructure.
- Claims about feelings/consciousness, universal sycophancy mechanisms, uniqueness/necessity,
  frontier-model generalization, or a precise fraction mediated.
