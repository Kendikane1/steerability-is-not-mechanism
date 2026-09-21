"""P1-011 offline integration check; the backend cannot run a forward pass.

Run from repository root:
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run --locked --offline python notebooks/preflight_qwen_tokenizer.py
"""

import hashlib
import importlib.metadata
import json
import platform
from datetime import UTC, datetime
from pathlib import Path

import torch
from torch import nn

from steerability_is_not_mechanism.adapter_core import SinglePromptAdapterCore
from steerability_is_not_mechanism.engineering_config import load_engineering_config
from steerability_is_not_mechanism.qwen_preflight import prepare_qwen_tokenizer

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/phase1/p1-011"
RESULT = OUT / "tokenizer_preflight.json"


class EncodingOnlyBackend(nn.Module):
    """Sentinel only, not a Qwen model or synthetic scoring model."""

    def __init__(self) -> None:
        super().__init__()
        self.block = nn.Identity()
        self.calls = 0

    def forward(self, *args: object, **kwargs: object) -> None:
        self.calls += 1
        raise RuntimeError("This preflight must never execute a model")


if RESULT.exists():
    raise FileExistsError("Preserve the previous preflight before explicitly rerunning")
spec_path = ROOT / "configs/local_model_engineering.yaml"
spec = load_engineering_config(spec_path)
previous_path = ROOT / "outputs/phase1/p1-005/inspection.json"
previous_bytes = previous_path.read_bytes()
if hashlib.sha256(previous_bytes).hexdigest() != (
    "dc0a430e3d47c41e5bd2d03f4ae3eeecd2a4564c416c900d863dc1a4e1320aa2"
):
    raise ValueError("P1-005 reference artifact changed")
previous = json.loads(previous_bytes)
prepared = prepare_qwen_tokenizer(ROOT / "outputs/phase1/p1-005/tokenizer", spec)
backend = EncodingOnlyBackend().eval()
was_deterministic = torch.are_deterministic_algorithms_enabled()
was_warn_only = torch.is_deterministic_algorithms_warn_only_enabled()
try:
    torch.use_deterministic_algorithms(True, warn_only=False)
    adapter = SinglePromptAdapterCore(
        backend, backend.block, prepared.tokenizer, prepared.layout, torch.device("cpu")
    )
    ids = adapter.encode_decision_prompt(previous["messages"][0]["content"])
finally:
    torch.use_deterministic_algorithms(was_deterministic, warn_only=was_warn_only)
checks = {
    "all_input_ids_equal_p1_005": ids.tolist() == [previous["input_ids"]],
    "expected_shape": list(ids.shape) == [1, 48],
    "final_token_271": ids[0, -1].item() == 271,
    "site_13": prepared.layout.site.layer_index == 13,
    "hidden_width_1024": prepared.layout.hidden_size == 1024,
    "bare_options_32_33": prepared.layout.option_ids == (32, 33),
    "forward_calls_zero": backend.calls == 0,
}
record = {
    "scope": "real pinned tokenizer + encoding-only sentinel; no weights or model execution",
    "timestamp_utc": datetime.now(UTC).isoformat(),
    "revision": spec.model.revision,
    "checks": checks,
    "input_ids": ids.tolist(),
    "verified_files": prepared.verified_files,
    "config_sha256": hashlib.sha256(spec_path.read_bytes()).hexdigest(),
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "python": platform.python_version(),
    "packages": {
        name: importlib.metadata.version(name) for name in ["torch", "transformers", "tokenizers"]
    },
}
OUT.mkdir(parents=True, exist_ok=True)
RESULT.write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(checks, indent=2))
print("result_sha256", hashlib.sha256(RESULT.read_bytes()).hexdigest())
if not all(checks.values()):
    raise SystemExit("Preflight acceptance failed")
