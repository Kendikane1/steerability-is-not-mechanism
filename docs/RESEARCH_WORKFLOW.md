# Working method

## Status and authority

On 2026-09-15 the user approved the proposed Phase 1 engineering iteration and requested
step-by-step learning with documentation for reproducibility. This begins Phase 1 planning;
exact engineering choices are still unresolved. Model downloads require separate authorization.
Pilot and locked execution are not authorized by this approval. AGENTS.md and the research
specification take precedence over workflow advice.

Background reading: Ethan Perez,
[Tips for Empirical Alignment Research](https://www.alignmentforum.org/posts/dZFpEdKyb9Bf4xYn7/tips-for-empirical-alignment-research).
His emphasis on quick feedback is useful; his workflow is explicitly illustrative for
interpretability. The procedure below is our project-specific adaptation, not a reproduction
of his workflow or adoption of its training/sampling methods.

## One meaningful question per iteration

Before a substantive check, record:

1. Question: the uncertainty that could change our next decision.
2. Prediction: expected observation, alternatives, and what would count against our explanation.
3. Smallest valid check: minimum implementation/data needed, including a relevant baseline.
4. Acceptance rule: technical tolerance or stopping condition, chosen before seeing results.
5. Scope: engineering, pilot, development, or locked; exact allowed split and authority.

Then implement/run only the authorized check, inspect its evidence, and record separately:
what happened, what it supports, what it does not establish, and the next discriminating check.
Change one diagnostic factor at a time when practical. Label exploratory multi-factor changes.
An unexplained failure is not a negative scientific finding; a bug fix is not positive evidence.
Do not repeat or alter valid analyses merely to obtain a desired direction of effect.

## Phase 1 sequence and acceptance targets

| Milestone | Minimum evidence before moving on |
| --- | --- |
| Specify input and measurement | Exact revision, template, option-token convention, hook boundary/index and precision recorded; ambiguities resolved before dependent work. |
| One synthetic binary example | Inspect actual input token IDs; independently check first-token option scores and their margin. No generated reasoning before the scored decision. |
| Capture and replacement | Capture-only and identity replacement preserve logits within declared tolerance; donor coordinate and orthogonal remainder verified; reverse edit and hook cleanup tested. |
| Small deterministic batch | Interrupted/resumed and uninterrupted runs agree under the declared protocol; completed IDs are not duplicated; incompatible resume metadata is rejected. |
| Engineering review | Full required checks, concise evidence report and walkthrough notebook; no inference about lovingness or sycophancy from engineering fixtures. |

The small model is Qwen3-0.6B on local MPS/CPU. Synthetic directions may test wiring but are
never named or interpreted as an independently validated lovingness direction. Scientific
direction extraction still requires independent loving-versus-neutral material.

Actual tokenizer inspection must be distinguished from a conceptual teaching example. Never
present guessed token boundaries or IDs as measured output. First-token log-probability margins
are model-output scores, not automatically calibrated confidence that an answer is true.

## Documentation without a second project-management system

- `RESEARCH_LOG.md`: chronological record of substantive actions, attempts, failures and results.
- `DECISIONS.md`: current choices and rationale; identify superseded decisions explicitly.
- Git and run metadata: exact code, configuration and artifact identity. Do not auto-commit.
- Ignored `outputs/`: raw logs and engineering artifacts, with stable paths referenced by the log.
  Before scientific work, establish durable private retention; Git-ignored does not mean backed up.

For each run retain the command, code commit plus patch/content hash if dirty, config hash,
input/fixture manifest and split identity, model/tokenizer revisions when applicable, environment,
device/dtype, seed, shard IDs, tolerance, timestamps, exit status and output/checkpoint paths/hashes.
Use explicit "not applicable" for conceptual work. Record deviations and failed attempts; do not
silently overwrite the only evidence. Do not log credentials or private runtime authentication.
Do not put locked items, item-level scientific outputs or sensitive data into a public work log.

Record each meaningful step, not each mouse click. A short entry can link to detailed machine
metadata. Label plans as plans and observations as observations. Preserve corrections with their
reason. At session end record what changed, the next question, and blockers/uncertainties.

## Iteration and learning boundaries

Explain one concept, invite the user's prediction, perform the smallest authorized check, and
review the outcome together. The user can slow down or ask for a different example at any time.
No daily run quota or requirement to keep the GPU busy. Suggested initial pacing: one bounded
question per focused session; adjust after observing actual implementation costs.

Phase 1 synthetic examples never enter scientific estimates. Pilot and development observations
can inform choices only within their declared rules, including the pilot's revision limits.
Keep every item family in one split. Locked-test outputs remain inaccessible until the required
freeze and explicit human execution action. During locked runs inspect only permitted operational
health information, not partial answer scores or hypothesis outcomes.

Do not add best-of-N answer selection, few-shot demonstrations, temperature tuning, training,
new models, or a substitute primary evaluator under the label of iteration. Such changes can
alter the question being measured; prohibited methods remain prohibited. Any permissible
scientific redesign needs explicit review and a recorded decision before execution.

Prioritize tool correctness, then phenotype/construct validity in the scientific pilot, then
development and the frozen test. A null result can be informative when the measurement and
controls are valid. Preserve rival explanations rather than treating all failures as obstacles
to a positive result. External human methodological review is useful before preregistration.
