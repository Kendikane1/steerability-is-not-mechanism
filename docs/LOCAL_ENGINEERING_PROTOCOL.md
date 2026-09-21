# Local measurement contract — p1-local-v1

Status: specified; one synthetic model scoring pass verified (P1-013). Capture/replacement and
repeatability remain unverified on Qwen. This engineering protocol consolidates P1-005 through
P1-008; it is not a scientific freeze or execution authorization. Source of current choices:
`DECISIONS.md`. Machine-readable settings: `configs/local_model_engineering.yaml`, validated
by `load_engineering_config` in `engineering_config.py`. All fields are required; unknown fields,
changed v1 constants, downloads and execution are rejected. A future protocol change needs an
explicit version/decision update, not a silent YAML tolerance change.

The existing `configs/local_smoke.yaml` remains the weight-free NumPy smoke configuration.
Its legacy model placeholders do not override the separate pinned engineering specification.
`sim-smoke --with-model` and `load_qwen_adapter()` remain unconditionally disabled.

## Adapter obligations before its first forward pass

Validation of YAML establishes declared settings only. The adapter/factory must verify actual
local artifacts against the recorded revision and file hashes, template hash, tokenizer output,
architecture (28 blocks, width 1024), effective device/dtype, attention implementation and runtime
settings. A filename or `revision` field alone is not proof of file identity. P1-005 recorded
tokenizer-file hashes; the separately approved weight retrieval and verification passed in P1-012.
Reject incompatible revisions, shapes, token conventions and stale runtime manifests.

Use one user message, no system message/tools, the pinned template and explicit non-thinking
flags. For each prompt, require nonempty input, round-trip text preservation, agreement between
template tokenization and encoding rendered text without added special tokens, and bare A/B
single-token prefix-preserving continuations (IDs 32/33). Return int64 IDs with shape `[1, T]`,
without padding. The adapter accepts its own validated IDs; reject empty, padded, batched,
wrong-dtype, wrong-device or out-of-vocabulary input before forward. A/B instructions do not
restrict the output vocabulary.

## Capture and replacement

- Site: `model.model.layers[13]` block output, after both residual additions and before the next
  block's normalization. Zero-based indexing. The encoded prompt determines `T`; never hardcode
  the teaching fixture's length in the adapter. Capture `output[0, T - 1, :]` as a detached clone.
- Expected output shape `[1, T, 1024]`; captured/replacement shape `[1024]`, float32 on the actual
  model device. Reject nonfinite values, wrong shape/dtype/device and a mismatched site.
- Replacement argument is a complete coordinate-edited vector constructed by the caller.
  Clone the block output, replace only the final input position and return that clone from the
  temporary forward hook. Other positions must be exactly preserved at this boundary.
- Register the hook for one forward call, require exactly one invocation and remove its handle
  in `finally`, including on exception. No concurrent calls on that adapter; reject re-entrancy.
  Capture-only returns no modified hook output. Identity replacement uses a clone of the original.
- Run full-prompt inference with no supplied past cache and `use_cache=False`, evaluation and
  inference mode. No token generation, training, optional external kernels or compilation.

## Scores and numerical audit

Return all final-position vocabulary logits as a finite float32 vector. Verification transfers
those values to CPU float64, calculates log-softmax over the full vocabulary, and subtracts the
user-endorsed option log probability from the correct option log probability. Independently
compare that margin to the corresponding raw logit difference. For the teaching fixture A is
correct and B is user-endorsed; future items must carry their own option roles.

P1-007 defines three baseline repetitions, capture-only/identity/zero-dose comparisons, elementwise
absolute-plus-relative tolerance, margin tolerance and the scaled projection/orthogonal audit.
Check actual float32 edited values after casting against CPU float64 reference math. The reference
direction is independently unit-normalized; engineering axis-aligned and dense synthetic fixtures
are never lovingness evidence. All measurements must be finite. Report errors even when within
tolerance. Never silently widen limits, change device/precision or substitute an alternate backend.

MPS is preferred when supported; a CPU fallback is a separate recorded run. Strict determinism
does not prove repeatability across hardware or releases. Manifest-driven shard/resume behavior,
storage budgets and the multi-hour gate remain milestone 4 work.

## Evidence boundary

P1-005 verifies tokenization for one synthetic prompt. P1-006/P1-007 specify source-derived
boundary and numerical choices. P1-008 verifies schema rejection and unchanged loader guards.
P1-009 implements shared mechanics in `adapter_core.py` using caller-supplied dependencies.
Synthetic CPU tests exercise token checks, final-position capture/replacement, identity behavior,
coordinate edits, output validation, re-entry rejection and exception-safe hook cleanup. The tiny
fixture has a four-number vector and a character tokenizer, explicitly distinct from Qwen.

The core trusts caller-supplied layout/provenance; it is not a Qwen factory or artifact verifier.
It requires evaluation/strict deterministic mode and rejects mixed precision; it does not set
process-global seeds/threads, choose a backend or verify weight files. Those responsibilities
belong to the separate guarded factory/runner. It accepts only token sequences validated by its own
encoder, tracked as hashes for this adapter's lifetime. Long-run lifecycle/resume policy remains
future work. At P1-009, no pretrained model logits, activations, memory fit, MPS support or real-model
repeatability had been validated. Synthetic tests cannot substitute for those runtime gates.

P1-011 adds `qwen_preflight.py`: verify the exact seven-file tokenizer/metadata bundle against
P1-005 hashes, reject unexpected or altered files, check architecture declarations, and load
only the local tokenizer with custom code disabled. The actual tokenizer passed the core's
encoding checks and reproduced all P1-005 input IDs with a backend that forbids forward calls.
This verifies tokenizer integration; it does not instantiate Qwen or validate its actual module
topology/runtime. Weight and loader authorization remain separate; see `LOCAL_WEIGHT_DOWNLOAD_PLAN.md`.


P1-013 adds `local_qwen.py`, `configs/local_single_item.yaml` and
`notebooks/run_local_single_item.py`: a separate, narrowly scoped offline factory/runner tied to
this specification's content hash. Original loader/CLI and scientific guards remain intact.
Use sequential weight loading (`HF_DEACTIVATE_ASYNC_LOAD=1`) because default threaded MPS
loading stalled; supply generation configuration derived from verified model config to avoid
an unused file lookup; select explicit `mps:0` for exact tensor-device comparisons. See the log
for preserved failed attempts and diagnostic limits.

The first successful run reproduced all 48 input IDs, verified actual topology/device/dtype,
and scored one prompt in float32 on MPS without generation or hooks. Full-vocabulary A/B
probabilities were 0.9097180193 / 0.0888515165; correct-minus-endorsed margin was 2.3261680603,
with zero discrepancy across three arithmetic calculations. Actual MPS driver allocation after
forward was 3,416,932,352 bytes; this is not peak memory or proof of long-run headroom.
No causal edit, pressure comparison, lovingness direction or scientific effect was measured.
