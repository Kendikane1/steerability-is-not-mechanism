# Phase 1 milestone 5 — engineering evidence review

Date: 2026-09-22. Record: P1-017 in `RESEARCH_LOG.md`.

## Verdict

The five **bounded local engineering milestones** have been implemented and reviewed.
Saved evidence supports the tokenizer boundary, scoring, capture, coordinate replacement and
short interrupted/resumed execution on this Mac. One historical console checksum needs the
explicit amendment below; the saved numerical results and checkpoint hashes are intact.

**The full engineering gate before the scientific pilot is not yet met.**
`RESEARCH_SPEC.md` requires resumable multi-hour execution and safe GPU-memory headroom.
Neither was established by these short checks. Scientific decisions, independent direction
material and required controls also remain unresolved. Pilot and locked execution remain disabled.

This review made **zero new model forward calls**. Recomputing a score from a saved array is
fresh verification of historical evidence, not a fresh model run or scientific evidence.

## Evidence by milestone

| Milestone | Historical evidence freshly checked | Scope and limit |
|---|---|---|
| 1. Specify model and boundary | P1-005 tokenizer bundle and inspection; pinned local weight checksum | Qwen3-0.6B revision `c1899de289a04d12100db370d81485cdf75e47ca`; engineering only |
| 2. Inspect one binary example | P1-013 full-vocabulary saved logits reproduce P(A)=0.9097180193, P(B)=0.0888515165, margin=2.3261680603 | One synthetic question; no generated answer or scientific inference |
| 3. Capture and replace | P1-014 six passes have exactly equal logits; P1-015 zero-dose/repeat passes are unchanged and paired/reverse applied vectors pass geometry checks | One site, two fixed synthetic directions; neither is a lovingness estimate |
| 4. Shard and resume | P1-016 four jobs across two shards, actual SIGKILL before commit, completed work preserved, 16 arrays exactly equal after resume | Short local process-crash recovery; not multi-hour, power-loss or remote durability |
| 5. Review and verify | Current tests, style, type checks, synthetic smoke and executed evidence-only notebook | Current fixes have synthetic regression evidence; original model runs remain historical |

For the high-pressure fixture, the input has 48 tokens. Bare answer labels are A=32 and B=33.
The first answer-token distribution is the model's next-token distribution after that entire
input. We score those two entries without restricting the vocabulary or sampling a token.
The pre-answer vector is at zero-based input position 47, token 271 (two newlines), at the output
of decoder block 13 after its residual additions. The low-pressure fixture has 51 tokens and
uses position 50. These are verified engineering choices, not a selected scientific layer.

The historical paired prompts did not demonstrate sycophancy: the high-pressure correct-minus-
endorsed margin was greater than the low-pressure margin. Small changes after synthetic edits
show that the intervention machinery can affect scores, not a lovingness-specific mechanism.

## Two review findings

### Existing database size limit

SQLite can return a higher `max_page_count` than requested if an existing database already
exceeds that limit. Previously the constructor ignored the returned value. A regression test
reproduced the failure by lowering the budget around an existing checkpoint. The constructor
now rejects that case, and the test also confirms that its saved result survives the refusal.
The actual 64 MiB engineering limit is unchanged. This changes storage validation, not model math.

### Console checksum recorded before a delayed writer finished

The first evidence notebook correctly stopped on a checksum mismatch in
`outputs/phase1/p1-016/check-01/interrupted-0.console.log`.
The original report's SHA-256 matches **exactly the first 4,735 bytes** of the current file:

- Original prefix SHA-256: `b197b5a51c130a86c1baabccbbabc4329d3f9ecf00a21aaacb3ab05d408cc9bf`.
- Current 5,021-byte file SHA-256: `3b7127368810d8f9a3ca0f66e597e51084adaadbe68e968695a192dd08e2a1b8`.
- The additional 286 bytes are Python's `resource_tracker` warning about one leaked semaphore
  during shutdown. This is consistent with the deliberately killed worker's cleanup process
  retaining the log handle after its main process exited.

The original report and console remain unchanged. This review pins both hashes and the exact
prefix length; its explicit amendment accepts only this specific observed file, not arbitrary
appended content. All other recorded console hashes, attempt records, checkpoint files and saved
arrays passed their checks. The original report's full-log checksum was premature; it must not
be described as matching the full current console.

Future supervisor runs now drain an output pipe until all inherited writers close it before
hashing the log. Synthetic subprocess tests verify a delayed descendant's output is retained
and unfinished output cannot be certified. A deadline failure aborts verification. This updated
supervisor has not been rerun against Qwen during this review.

## Reproduce the review

The tracked notebook `notebooks/phase1_engineering_review.ipynb` is a client of the read-only
audit in `notebooks/review_phase1.py`. It needs the existing ignored historical artifacts and
verified local model file for hashing; a fresh clone alone is insufficient. It never downloads
missing files or loads the model. Missing or changed evidence is an error.

Use an unused output directory:

```sh
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run --locked --offline \
  python notebooks/run_phase1_review.py --output-dir outputs/phase1/review-reproduction-01
```

The launcher uses this project's Python kernel and saves both an executed notebook and JSON
summary. P1-017's successful execution is in `outputs/phase1/p1-017/notebook-03/`; failed
`notebook-01/` is retained. All142 tests, lint, formatting, type checks, the synthetic smoke and all five notebook code
cells passed. Fresh verification logs and source hashes are in
`outputs/phase1/p1-017/verification-02/verification.json`.

The runtime source changes intentionally make old checkpoints incompatible with a new run's
identity. They remain readable as historical evidence. Do not edit their identities or migrate
them to bypass the resume guard.

## Recommended next bounded step

Specify a sustained **local synthetic** workload and its acceptance criteria before running it:
duration, fixed manifest and shard sizes, interruption schedule, memory measurements, abort
limits, numerical tolerances and disk budget. Measure peak usage and available capacity, not
only allocation after a run. Then validate that protocol in a small dry run before a multi-hour
run. This is a recommendation, not a newly enabled workload or a scientific design decision.
Remote scientific-model memory and reproducibility checks require their own scope and authority.
