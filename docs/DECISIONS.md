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

### Phase 1 workflow approved 2026-09-15

- User approved the five-milestone engineering iteration: specify measurement, inspect one
  synthetic example, validate capture/replacement, validate sharded resume, review evidence.
- Begin with stepwise explanation and decision documentation. Follow `RESEARCH_WORKFLOW.md`
  and maintain `RESEARCH_LOG.md`; user understanding is part of the working method.
- This is approval to begin Phase 1 planning/engineering within existing guards, not approval
  for model downloads, scientific data generation, pilot execution or locked execution.
- Exact choices below remain open. The article discussed with the user is background advice,
  not authority to add training, sampling selection or change the primary outcome.

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

- P1-013 verified one float32 MPS scoring pass. Sustained memory headroom remains unknown;
  P1-014 passed within-process repeatability and capture/identity checks for one prompt/site.
- Generalize the P1-005 token-boundary assertions to the eventual adapter and all engineering
  prompts; one synthetic prompt passed model-backed first-token scoring in P1-013.
- P1-014 verified capture and identity at the selected block-output site. Nonzero coordinate
  replacement and reverse replacement passed on the P1-015 synthetic pair/directions.
- P1-015 verifies bounded Qwen coordinate/reverse replacement; scientific generalization and
  long-job guarantees remain unestablished. Failure cleanup is also covered by synthetic tests.
- P1-016 specifies the bounded local shard/checkpoint/resume protocol below; multi-hour
  operation, crash/power-loss durability across systems and scientific execution remain unverified.

### P1-005 / Local tokenizer protocol established 2026-09-15

- Pin the local engineering model/tokenizer repository to `Qwen/Qwen3-0.6B` commit
  `c1899de289a04d12100db370d81485cdf75e47ca`; license file records Apache-2.0.
  Only tokenizer and metadata files were retrieved. Model weights were neither retrieved nor
  validated. This pin does not select a scientific model or authorize a weight download.
- For the inspected single-user synthetic prompt, use the revision's unmodified chat template
  with `add_generation_prompt=True`, `enable_thinking=False`, `return_dict=False`.
  No added system message, tool definition or manually appended answer prefix.
- Engineering answer convention: bare `A` / `B`, token IDs 32 / 33. Both pass single-token,
  round-trip and prompt-prefix preservation checks. Space-prefixed ` A` / ` B` are distinct
  tokens 362 / 425; do not silently pool them into the bare-label score. Scientific validity
  and exclusion rules remain open before the pilot.
- The concrete input boundary is the last non-padding token of the fully formatted input,
  including the empty thinking section and trailing newlines. In this 48-token fixture it is
  zero-based index 47, token 271 (`\n\n`), after `</think>`. The current abstract name
  `pre_answer_final_assistant_delimiter` must not be interpreted as an earlier header token.
  Hook placement and layer indexing remain unresolved; this is token evidence only.
- Retokenizing an extra newline plus a label merges that newline with the prompt's trailing
  newlines, changing its last token. This is a text-tokenization result; already supplied
  input IDs do not change during model generation.
- Keep executable configs guarded and unresolved until the remaining measurement choices are
  specified together. This engineering protocol does not freeze scientific prompt wording.
- Evidence and reproduction: P1-005 in `RESEARCH_LOG.md` and
  `notebooks/inspect_tokenizer_boundary.py`; raw artifacts in `outputs/phase1/p1-005/`.

### P1-006 / Local engineering activation boundary specified 2026-09-15

- Use the residual-stream output of `model.model.layers[k]` in `Qwen3ForCausalLM`, after
  both attention and MLP residual additions. This is before the next block's input RMSNorm;
  for the last block it is before the model's final RMSNorm. Do not capture the normalized
  attention/MLP branch input or the attention/MLP update alone.
- Index blocks from zero: `k=0` means the first transformer block. Pinned 0.6B configuration
  specifies 28 blocks (indices 0 through 27), with vectors of width 1024. No particular `k`
  is selected in this entry. Scientific layer selection remains development-only and open.
- Token position is P1-005's final non-padding formatted input token. For initial one-prompt,
  unpadded engineering calls, select `output[0, input_length - 1, :]`. Expected block output
  shape for the 48-token fixture is `[1, 48, 1024]`; this is a source-derived expectation,
  not an observed activation. Later padded batches must locate the last non-padding index
  explicitly; do not generalize `-1` to arbitrary padding layouts.
- Intended implementation: a temporary `register_forward_hook` on the selected block. The
  installed Qwen3 block returns a tensor. Capture a detached clone of the selected vector;
  for intervention return a cloned output with only that position replaced by the coordinate-
  edited vector. Other token positions are unchanged at this site. Remove the hook in `finally`,
  including when execution raises an exception. No permanent library edits or weight edits.
- Initial measurement design: evaluation/inference mode, one full prompt forward pass with
  `use_cache=False`, no generated tokens or past-key-value cache supplied. Score bare A/B from
  the final input position's logits after downstream computation. A returned hidden-state
  collection is not assumed to have the same indexing/boundary as this explicit block output.
- Rationale: the complete block output is an explicit, inspectable residual vector passed
  onward; selecting it avoids conflating a component's update with the accumulated activation.
  This is an engineering convention, not evidence it is a privileged scientific site.
- Evidence: installed Transformers 5.15.0 Qwen3 source and PyTorch hook source inspected in
  P1-006 (`RESEARCH_LOG.md`). Runtime hook behavior, numerical tolerances, precision and the
  complete adapter implementation are still unverified. Executable guards remain unchanged.

### P1-007 / Initial engineering block and numerical protocol, 2026-09-15

- Use block index 13 (the 14th of 28 blocks), at P1-006's complete block-output boundary.
  Rule: choose the output halfway through the stack, leaving 14 blocks downstream. This
  exercises downstream propagation without choosing a site from answer effects. No layer
  sweep, lovingness direction or scientific layer choice is implied.
- Initial model/activation/edit dtype: float32, no quantization or automatic mixed precision.
  This retains the smoke config's existing precision choice and reduces rounding concerns
  compared with 16-bit arithmetic. It does not recover precision absent from saved weights.
  Device order remains MPS when supported, then a separately recorded CPU run. Memory fit
  and full-operation support require later checks; do not silently lower precision on failure.
- Initial attention implementation: explicit `eager`, using the inspected Qwen3 attention
  code; no compilation or optional external kernels. One unpadded prompt per call, evaluation
  plus inference mode, `use_cache=False`, and no sampling. Seed Python, NumPy and PyTorch with
  1729 before each independent run; use one CPU intra-op and inter-op thread, set at process
  startup. Record actual runtime settings in the manifest.
- Enable `torch.use_deterministic_algorithms(True, warn_only=False)`. An unsupported-operation
  error is a recorded failure; assess a complete CPU fallback run while retaining the strict
  setting. Numerical mismatches require investigation rather than automatic device switching
  or tolerance relaxation. The switch is not proof of application-level reproducibility.
- Predeclare initial same-device, same-environment acceptance: all compared values finite;
  each captured activation/logit element obeys `abs(actual - reference) <= 1e-5 +
  1e-5 * abs(reference)`. Compare three identical baseline passes, capture-only, cloned identity
  replacement and zero-coordinate-difference replacement against the unhooked baseline.
  Record exact equality as well as maximum errors. Identity passes are expected to be exactly
  equal; any nonzero discrepancy is reported even if it passes the numerical gate.
- Additionally require bare-A/B log-probability margin discrepancy <= `1e-4` absolute for those
  no-change comparisons. Compute verification scores from saved float32 logits on CPU float64,
  including a log-softmax versus logit-difference cross-check; this does not make model execution
  float64. These bounds are chosen engineering stopping rules, not measured error estimates or
  thresholds establishing a meaningful scientific effect. Cross-device equality is not assumed.
- Coordinate-edit audit, including reverse: inspect the actual float32 replacement after casting,
  on CPU float64 using the reference unit direction. With `S = max(1, ||h||2, ||h_edit||2,
  abs(target_coordinate))`, require projection error <= `1e-5*S` and orthogonal-remainder
  difference L2 norm <= `1e-5*S`. Unedited positions must be exactly unchanged at the hook output.
  Existing NumPy float64 functions are reference math, not an MPS implementation. A dense
  synthetic direction must accompany a simple axis-aligned fixture in later wiring tests.
- Failure policy: preserve all failed results; diagnose inputs, code and backend. Do not widen
  tolerances to pass a run. Any justified protocol revision must be explicit, logged and made
  before a new run; original evidence remains available. Freeze separate numerical/resume gates
  for the eventual scientific precision and task regime.
- Status: selected initial engineering protocol, awaiting implementation and measured validation.
  Executable configs, loader guards, weights authorization and scientific constraints unchanged.

### P1-008 / Guarded configuration and adapter contract, 2026-09-15

- Consolidate P1-005–P1-007 as `p1-local-v1` in `configs/local_model_engineering.yaml`, loaded
  separately with `load_engineering_config`. All fields are explicit/required; unknown fields
  and incompatible v1 constants are errors. The declaration is frozen after validation.
- Status is `specified_unverified`; download and execution flags are fixed false. This schema
  does not implement runtime checks, prove file identity or authorize model loading. A future
  execution path requires a separate reviewed change and the user's weight-download permission.
- Preserve `configs/local_smoke.yaml` as the existing NumPy fixture runner configuration;
  its legacy revision placeholders do not select a model. Pilot/locked configs are unchanged.
- `ActivationSite` now explicitly identifies block output and rejects invalid index/boundary
  declarations. The 0.6B-specific site is index 13; the general site class has no scientific
  model-specific upper bound. The future adapter must check its loaded architecture and site.
- `docs/LOCAL_ENGINEERING_PROTOCOL.md` defines input/output shapes, per-prompt tokenizer checks,
  artifact/runtime validation, hook lifetime and numerical audit obligations. The adapter
  remains an interface plus an unconditionally guarded loader; no hooks have been implemented.
- Weight-free tests validate configuration rejection and unchanged loader/CLI guards. Runtime
  capture/replacement, numerical stability, memory fit and deterministic resume remain untested.

### P1-009 / Shared adapter mechanics, 2026-09-17

- Implement reusable `SinglePromptAdapterCore` with injected model/block/tokenizer dependencies.
  It loads no files or weights; `load_qwen_adapter`, CLI and configuration execution guards
  remain unchanged. Caller-supplied revision/layout are declarations, not verified provenance.
- Core checks template hash, encoding/round-trip/prefix consistency, input ownership/range,
  shapes/dtype/device/finiteness, evaluation and strict deterministic mode, and absence of
  mixed precision. Capture is a detached clone. Replacement copies the full block output and
  edits only the final position. A per-instance lock rejects concurrent/re-entrant calls;
  hooks require exactly one invocation and are removed in `finally`.
- Provide `observe` to obtain pre-edit activation and final logits in the same forward call;
  retain the existing adapter interface methods as wrappers. This makes capture-only comparisons
  testable without equating observations from different forward passes.
- Synthetic CPU fixtures use a character tokenizer and analytic four-dimensional causal prefix
  sum, not Qwen or a learned direction. Natural-coordinate and reverse checks use two observed
  fixture activations with axis-aligned and dense synthetic directions. Reference NumPy float64
  edits are cast to float32 before application; this does not yet implement device-native
  float32 coordinate-construction math.
- Real Qwen construction must still verify architecture/module identity, files/revisions,
  tokenizer compatibility and all runtime settings before use. Weight authorization, memory
  feasibility, MPS/model checks and resumable execution remain unresolved; scientific gates
  are unchanged. Shared mechanics are synthetic-tested, not a completed Qwen integration.

### P1-011 / Verified tokenizer preflight and proposed weights, 2026-09-17

- `qwen_preflight.py` verifies the exact P1-005 tokenizer/metadata allowlist against previously
  recorded hashes, rejects missing/extra/modified/nonregular entries, checks pinned architecture
  declarations and loads only the local tokenizer. No weights/model constructor is involved.
- The real tokenizer satisfies the shared core's encoding checks for the original synthetic
  prompt and reproduces all 48 recorded IDs. A forward-forbidden sentinel makes this evidence
  distinct from a pretrained-model run. Model topology and runtime verification are still open.
- Proposed one-file local weight retrieval and checksum verification are specified in
  `LOCAL_WEIGHT_DOWNLOAD_PLAN.md`. The official metadata size is 1,503,300,328 bytes. User
  download permission is pending; no weights were fetched and all execution guards remain closed.
- Local installed memory is 8 GiB; observed free disk is about 38 GiB. Neither value proves
  adequate runtime headroom. Future model/device checks must use fresh machine state.

### P1-012 / Weight download authorized, 2026-09-17

- User explicitly approved the one-file 1.50 GB pinned Qwen3-0.6B download described in
  `LOCAL_WEIGHT_DOWNLOAD_PLAN.md`, including byte-count and SHA-256 verification.
- This supersedes P1-011's pending-download-permission status only. Scope is local download
  and integrity verification; no model loading/forward pass or scientific execution is included.
  Keep loader/CLI/config guards unchanged. Transfer outcome belongs in `RESEARCH_LOG.md`.
- Completed: local file matched 1,503,300,328 bytes and the approved SHA-256, then was published
  under the pinned revision directory in ignored `models/`. This establishes file integrity,
  not model runtime compatibility, memory headroom or any scientific result. No model was loaded.

### P1-013 / Scoped first local forward, 2026-09-17

- User's post-download `continue`, together with the approved Phase 1 plan, authorizes the next
  bounded synthetic scoring step. P1-012's download-only scope is complete; no scientific run
  or additional download is authorized.
- Add separate `configs/local_single_item.yaml`: exact original synthetic prompt, one forward
  call, A correct/B endorsed, pinned weight checksum and exact P1-008 specification content hash.
  Unknown/changed scopes, prompts, call budgets and hashes are rejected; disabled requests fail
  before artifact access. This explicit runner leaves the general loader, smoke CLI and all
  pilot/locked guards intact. The declarative engineering specification remains non-executable.
- `local_qwen.py` verifies local tokenizer/weights and reviewed implementation hash, configures
  fresh-process seed/threads/strict determinism and loads directly to the selected local device
  in float32 with eager attention and no external kernels/cache. Verify checkpoint loading report,
  actual classes, layer count, embedding shape and parameter/buffer device/dtype before scoring.
- One-item runner saves full final-token vocabulary logits and computes A/B probabilities plus
  margin in CPU float64. Cross-check torch log-softmax, NumPy metric and raw logit difference
  with absolute tolerance `1e-12`. This is an arithmetic identity check, not a scientific threshold.
  No generation, capture/replacement hooks, pressure comparison or repeatability claim in this run.
- Attempt MPS first; never enable implicit per-operation fallback or alter float32 settings to
  pass. A whole-run CPU fallback, if required, must have a distinct run record and retain failures.
  Resource and model-backed outcome evidence is recorded in P1-013 of `RESEARCH_LOG.md`.

- Loading diagnostics: use `HF_DEACTIVATE_ASYNC_LOAD=1` for this local runner. Default
  threaded MPS loading stalled; sequential loading completed. This is an operational workaround,
  not a proven library root cause. Supply `GenerationConfig.from_model_config(config)` to prevent
  an unnecessary generation-file lookup; direct scoring never uses generation. Select MPS as
  explicit `mps:0` so strict device comparisons match actual tensor device identities.

### P1-014 / Bounded capture and identity audit, 2026-09-21

- Continue the approved Phase 1 engineering sequence after publishing `bd7c705` at the user's
  request. Add `configs/local_noop.yaml` with distinct literal scope and exactly six maximum
  forward calls: three baselines, capture, identity replacement, post-hook baseline.
- Share artifact verification/construction through a private loader helper; keep the existing
  single-item request at one call and reject crossing request schemas. General/scientific loader
  guards and the frozen engineering specification are unchanged. Sequential loading is required.
- Use the same original synthetic prompt and site13, compare every logit and A/B margin against
  baseline1 using existing P1-007 limits. Compare pre-edit captures across capture/identity calls.
  Preserve raw vectors, exact equality, maximum absolute errors and per-call hook cleanup.
  Stop at first discrepancy outside tolerance, retaining partial evidence. No altered coordinate
  or direction is introduced. Zero-dose coordinate math and bidirectional edits are later checks.
- Outcome: all six passes and captured vectors matched exactly; max logit/activation/margin
  discrepancies were zero. Hooks removed after every call; details/artifacts in the research log.
- Scope of a pass is this prompt/site/device/environment within one process. It does not establish
  cross-process, cross-device or scientific reproducibility, nor a lovingness-related mechanism.

### P1-015 / Synthetic coordinate and reverse audit, 2026-09-21

- Add distinct `synthetic_paired_coordinate_v1` request, max18 calls, fixed original prompt and
  counterpart `Please correct me if I am wrong.`. Shared verified artifacts; no general or
  scientific guards relaxed, no changes to earlier request scopes or frozen protocol.
- Preselect axis0 and unit alternating-sign dense directions, independent of all measured
  outcomes. These are engineering fixtures, not lovingness estimates or matched-random controls.
- Use existing NumPy float64 reference coordinate math and actual float32 device replacements.
  Extend observation records to expose the actual applied vector and exact equality of unedited
  token positions. Verify donor projection and orthogonal preservation against P1-007 limits.
- Three baselines and capture per context; zero-dose and counterpart-coordinate swaps in both
  contexts for each direction; final baseline per context. Require no-change scores within
  existing bounds, pre-edit activation repeatability, clean hooks and valid geometry. Score
  direction/magnitude is descriptive only. No scientific phenotype or mechanism claim follows.

- Outcome: all18 passes and saved-array audit passed. No-change scores/captures were exactly
  equal. Axis geometry exact; dense rounding error below predeclared bounds. This synthetic pair
  did not show the intended pressure-lowers-correctness pattern. Do not revise it to force one;
  scientific phenotype validation belongs to a separately designed pilot.
- Keep float64 reference construction followed by float32 application for this engineering
  implementation; a device-native coordinate constructor is not yet implemented or verified.
  Next bounded step is shard/resume engineering, not scientific execution.

### P1-016 / Local deterministic shard/resume protocol, 2026-09-22

- Fixed four jobs on the P1-015 synthetic pair: capture and dense counterpart-coordinate edit
  in each context. Job IDs and seeds are immutable; two shards use the existing SHA-256 mapping
  and sorted IDs. Shard0 has three jobs; shard1 has one. Each edit computes its own donor/source
  captures, avoiding checkpoint dependencies between jobs. No additional scientific items.
- SQLite per local shard with rollback journal, synchronous FULL, one writer transaction spanning
  compute/insert/commit, unique result ID and SHA-256 of canonical metadata plus payload. Locks
  are OS-managed; never delete a stale lock manually. Concurrent writers fail closed. Completed
  rows are verified/skipped; unfinished transactions are recomputed, not counted as completed.
- Store only result arrays/metadata, not model state. Max2 MiB array payload/job and64 MiB DB/shard;
  these are small engineering limits, not a scientific retention plan. Raw outputs remain ignored.
- Resume identity includes fixed manifest, source/lock/protocol hashes, strict request values,
  actual device, Python/platform/packages, SQLite and runtime environment. Changed identity or
  corrupt completed records is an error before lazy model construction. No automatic migration.
- Compare uninterrupted versus SIGKILL-before-commit/fresh-process resumed outputs with the
  existing element1e-5 absolute+relative and margin1e-4 limits, also reporting exact equality.
  Require no committed-row duplication/recomputation, partial-row rollback and zero-work replay.
- Bound claim to this synthetic workload on the local Mac/filesystem. This does not establish
  multi-hour reliability, hard power-loss durability, shared/network filesystem support or remote
  CUDA/scientific-job resumability. A completed run is not a private backup strategy.

- Measured P1-016 outcome: four unique completed jobs and16 saved arrays match the uninterrupted
  reference exactly after a real SIGKILL-before-commit and fresh-process resume. The committed job
  is preserved/skipped, unfinished work reruns, completed replay performs zero model work, and
  changed-device identity is refused before load. Milestone4's short local acceptance is passed;
  the broader operational limitations above remain open. P1-017 reviews this evidence below.

### P1-017 / Consolidated review, 2026-09-22

- Five bounded local milestones are reviewed; this does not close the full engineering gate in
  `RESEARCH_SPEC.md`. Resumable multi-hour execution and safe GPU-memory headroom remain open.
- Saved numerical evidence and checkpoint hashes pass a fresh offline audit. Preserve the
  original P1-016 report and console; record an explicit amendment for the delayed 286-byte
  shutdown warning appended after the interrupted console's recorded checksum. Details and
  exact hashes: `PHASE1_ENGINEERING_REVIEW.md`. No generic checksum exception is permitted.
- Reject existing checkpoints larger than the unchanged 64 MiB budget. Finalize future worker
  logs at pipe EOF, including inherited writers, before hashing. Both fixes have synthetic
  regression tests; no new model inference was performed for this review.
- Keep strict source identity: changed code refuses old checkpoints rather than migrating them.
  Old results remain valid historical evidence under their recorded source identities.
- Next recommendation is a predeclared sustained local synthetic protocol with memory/abort
  criteria and a small dry run. No scientific layer, direction or pilot choice is settled here.

### P1-018 / Sustained-test planning, 2026-09-23

- User approved publishing the milestone4–5 checkpoint and preparing the next bounded plan.
- `LOCAL_SUSTAINED_TEST_PLAN.md` proposes a12-cycle rehearsal, then two sequential arms targeting
  two active hours each, with fixed synthetic jobs, natural counterpart edits and one planned
  interruption. Counts/resource thresholds are draft recommendations pending implementation and
  rehearsal; this does not authorize a new long run or settle scientific choices.
- Keep P1-016 budgets unchanged; any sustained runner needs a distinct reviewed request.
  Freeze monitoring, manifest, limits and fault budget before execution. Sampled memory maxima
  must not be labeled guaranteed peaks. Remote1.7B headroom remains a separate requirement.

### P1-019 / Approved limits and resource refusal, 2026-09-23

- User approved the proposed P1-018 limits and proceeding through completion, conditional on
  the stated gates. This supersedes P1-018 planning-only authority, not scientific restrictions.
- Startup requires macOS dispatch pressure1;2/4 and unknown readings refuse. Read-only sysctl
  timeouts are2 seconds each; total sample age must be at most5 seconds. Units/parsers and all
  threshold boundaries have weight-free tests. No missing reading is replaced by a passing value.
- Live startup preflight refused pressure2 (warning), before importing torch or loading a model.
  Disk passed the10 GiB startup requirement. Absolute existing swap is recorded, not mistaken
  for post-baseline swap growth. No rehearsal or long-run conclusion follows from this refusal.
- Full sustained runner/continuous monitor remains incomplete. Next is to restore normal host
  pressure, then complete the runner/monitor and verification before any model-backed rehearsal.
  Do not automatically close unrelated applications, reset swap or bypass the startup gate.

### P1-020 / User-authorized warning-pressure rehearsal revision, 2026-09-23

- User explicitly overrides automatic stopping at warning memory pressure for this local test.
  Record warning readings; critical/unknown pressure still stops, as do unchanged swap, disk,
  MPS allocation, monitoring and numerical limits. This is an explicit prospective protocol
  revision, not a retroactive pass of P1-019 or the original normal-pressure headroom criterion.
- Implement a distinct96-call,12-cycle rehearsal request and supervisor. Budget193 attempted
  forwards for reference plus one interrupted/resumed comparison; replay/incompatible probes0.
  Details and deadlines in `LOCAL_SUSTAINED_TEST_PLAN.md`, frozen before model execution.
- Calibrate duration/storage only after rehearsal acceptance. If a remaining limit fails,
  stop/preserve/diagnose autonomously; do not relax it or automatically enter scientific work.

- Measured P1-020 outcome: revised warning-pressure startup proceeded, but the first worker
  exceeded the unchanged256 MiB swap-growth limit during loading and was stopped before any
  forward. Rehearsal not passed; no long-run count/arms. See `SUSTAINED_REHEARSAL_RESULT.md`.
  Preserve current limits and diagnose competing memory demand before another attempt.

### P1-021 / Read-only remote assessment, 2026-09-23

- Existing remote is reachable; fresh GPU/environment/disk metadata support preparing a bounded
  CUDA engineering check. Details and the proposed first test: `REMOTE_READINESS_REVIEW.md`.
- Preserve dirty remote checkout; do not pull/reset it. Dependencies match the local lock;
  separate CUDA package/device handling and an explicit remote0.6B engineering scope are needed.
- No remote weight transfer/download, code deployment or model workload was authorized/executed
  in this readiness check. Remote host RAM is still8 GiB; free VRAM alone cannot establish fit.
  Scientific1.7B FP16 and pilot decisions remain open.

### P1-022 / Remote engineering continuation, 2026-09-23

- User authorized reconciliation, verified transfer of existing pinned0.6B artifacts, and bounded
  synthetic CUDA checks. Preserve old remote changes in verified private backup plus Git stash;
  remote main fast-forwarded to d1ff9bd. Reviewed local work remains uncommitted on both hosts.
- Use distinct CUDA-only request/runtime with float32, eager attention, strict determinism and
  IEEE matmul; keep all Mac scopes and scientific guards unchanged. See
  `REMOTE_ENGINEERING_PROTOCOL.md` for budgets and Windows resource limits.
- Single score passed; mechanics and short Windows process-tree interruption/resume supervisors
  subsequently returned passed. These are short engineering checks, not multi-hour or scientific
  results. After a transient SSH interruption, the remote artifact/checkpoint audit passed;
  all16 resumed arrays match the uninterrupted reference exactly. See `REMOTE_ENGINEERING_RESULT.md`.
- Windows virtual-environment launcher and worker can have different PIDs. Verify ownership and
  terminate the owned tree; real weight-free shutdown probe and185 tests on both hosts pass.
- Next gate: a separately scoped12-cycle CUDA rehearsal and measured
  storage/duration feasibility. Do not run sustained work through the existing small call budgets.

### P1-023 / CUDA rehearsal and manual execution, 2026-09-24

- Separate12-cycle/193-attempt comparison protocol: `REMOTE_REHEARSAL_PROTOCOL.md`. Initial
  attempt stopped on Windows progress-file replacement denial after12 recorded forwards and
  six committed jobs. No rehearsal or storage-feasibility pass follows from that attempt.
- Verified bounded Windows-only metadata publication retry: at most1 second, persistent errors
  still fail. Real Windows reader-lock probe and190 tests on both hosts pass. Old checkpoints
  remain source-bound and are not migrated. All model/resource/scientific limits unchanged.
- For usage efficiency, user can run the prepared manual launcher without Codex supervising;
  return its saved summary for evidence review. Manual rehearsal-02 subsequently stopped during
  loading with0 forwards: available physical RAM336.73 MiB and load95%, while commit reserve
  still passed. Preserve limits and inspect/reduce Windows background demand before a new attempt.

### P1-023 / Manual attempt03 reported outcome

- User-reported supervisor result: rehearsal passed with96/49/48/0/0 forwards; projected long-run
  full-array storage184.022 GiB fails the unchanged4 GiB cap. Raw artifact audit remains pending.
- Do not launch the multi-hour test under this storage plan. Next assess lossless byte-identical
  array deduplication on saved outputs, preserving every unique array and per-job identity; this
  is a proposal pending validation and a prospective protocol revision, not an adopted shortcut.

### P1-024 / Rehearsal audited; lossless archive prototype validated

- Independent saved-evidence audit passed:192 across-arm arrays exactly equal. The reported
 184.022 GiB naive long-run projection is reproduced; existing4 GiB cap stays unchanged.
- Lossless full-payload sharing reconstructs96 job records exactly from4 unique bundles;
  storage85.10 MiB becomes3.86 MiB without removing original files or result information.
- Conditional long-run estimate1.44 GiB supports a prospective shared-bundle design. Preserve
  every unique payload and job record; bind one complete immutable manifest by hash in shards.
  This design is not yet a live resumable writer or a frozen long protocol. Require bounded-memory
  operation, blob-before-commit durability, corruption/interruption tests and a fresh short
  rehearsal before multi-hour execution. See `REHEARSAL_STORAGE_REVIEW.md`.

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

### P1-025 / Live compact storage for a separately scoped short rehearsal

- Adopt a per-arm SQLite payload catalog with the complete immutable identity/manifest once;
  shard headers bind its hash and at most16 IDs. Exact byte equality alone permits sharing.
- Catalog commit precedes shard-reference commit, with FULL synchronization and DELETE journals.
  Preserve harmless unreferenced complete blobs after interruption; reject corruption rather
  than repairing/migrating. Each shard is verifiable with its retained catalog dependency.
- Keep all numerical, model and resource limits. New --compact identity separates changed
  writer evidence from old checkpoints. Catalog3 GiB ceiling is additional to total4 GiB cap;
  no increase in allowed output. Do not use the short supervisor's48-row collection at long scale.
- User can run the prepared foreground short launcher without agent supervision, return its
  summary, and stop on failure. Multi-hour calibration, streaming audit, memory-growth gate and
  disconnect-independent launcher remain separate pending work. No multi-hour command yet.

### P1-026 / Compact audit passed; long wall-time feasibility unresolved

- Fresh saved-artifact audit verifies the compact short rehearsal. Conditional storage estimate
  1.39 GiB fits4 GiB; direct measured short wall-time extrapolation is3.98 hours/arm versus the
  approved3-hour cap. This estimate has short-run/warm-up limitations, but does not justify launch.
- Keep the active-time minimum, wall cap and retention requirements. Profile overhead using
  saved results before optimizing/recalibrating. Do not freeze or launch the multi-hour protocol
  merely because compact storage passed. See COMPACT_REHEARSAL_RESULT.md.
