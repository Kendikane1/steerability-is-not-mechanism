# Local weight download — verified 2026-09-17

The user explicitly approved this download and integrity check on 2026-09-17 after reviewing
the request. This approval does not authorize a model run. P1-012 of `RESEARCH_LOG.md` records
successful transfer and exact byte-count/SHA-256 verification. No model was loaded or run.

## Exact artifact

- Repository: `Qwen/Qwen3-0.6B`, engineering only.
- Revision: `c1899de289a04d12100db370d81485cdf75e47ca`.
- Filename: `model.safetensors` (one file).
- Size reported by pinned repository metadata: **1,503,300,328 bytes**, about 1.50 GB / 1.40 GiB.
- Expected SHA-256: `f47f71177f32bcd101b7573ec9171e6a57f4f4d31148d38e382306f42996874b`.
- License record: Apache-2.0, verified tokenizer bundle's `LICENSE` file.
- Source metadata read 2026-09-17:
  [official pinned-revision API](https://huggingface.co/api/models/Qwen/Qwen3-0.6B/revision/c1899de289a04d12100db370d81485cdf75e47ca?blobs=true).
- Planned destination within the project:
  `models/Qwen3-0.6B/c1899de289a04d12100db370d81485cdf75e47ca/model.safetensors`.
  The `models/` directory is Git-ignored. Existing verified tokenizer files are already local.

## Approved transfer procedure

Download this one pinned weight file over HTTPS into a temporary `.part` file, with interruption
resume support, then verify byte count and SHA-256 against the record above. Promote it to the
final filename only after verification. Do not replace an existing verified file or automatically
fetch other models. Record the request, timestamps, command, byte count, checksum and outcome.
No credentials are required for this public artifact.

The planned source is the pinned Hugging Face resolve URL for the filename above. No weight
request, even a partial body request, has been made in P1-011. Reading repository metadata did
not download weights. Remote metadata is not a substitute for verifying the final local bytes.

## Resource snapshot and execution boundary

Read-only checks on 2026-09-17 report 8 GiB installed unified memory and about 38 GiB available
on the project filesystem. This establishes a storage snapshot, not model runtime headroom.
Float32 model execution needs more memory than the BF16 file size, plus intermediate buffers
and operating-system/application memory. Check live availability before the first model run.

This request is for **download and integrity verification only**. It will not start a Qwen
forward pass, enable scientific execution or change the locked/pilot guards. The loader/CLI
remain closed during this step. After download, the next bounded work is completing and
reviewing the local factory/runtime setup before the approved synthetic model-backed check.
