"""Offline tokenizer preflight only. Never constructs a model or downloads files.

Expected hashes are the P1-005 pinned-revision records. Authenticating new revisions requires
an explicit reviewed update; hashes are never learned from whichever files happen to be present.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .adapter_core import AdapterLayout, DecisionTokenizer
from .engineering_config import LocalEngineeringConfig

TOKENIZER_FILES = {
    "LICENSE": "832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e",
    "README.md": "1ab64a26fcb3b461423b89a433a8c858f1bf8d4086f979cbb3ff878d47cf20e9",
    "config.json": "660db3b73d788119c04535e48cf9be5f55bc3100841a718637ae695b442f27dd",
    "merges.txt": "8831e4f1a044471340f7c0a83d7bd71306a5b867e95fd870f74d0c5308a904d5",
    "tokenizer.json": "aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4",
    "tokenizer_config.json": "d5d09f07b48c3086c508b30d1c9114bd1189145b74e982a265350c923acd8101",
    "vocab.json": "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910",
}


def verify_file_bundle(directory: Path, expected: Mapping[str, str]) -> dict[str, str]:
    """Verify an exact flat bundle of regular files against trusted caller-supplied hashes."""
    if not expected or any(
        name in {"", ".", ".."}
        or "/" in name
        or "\\" in name
        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        for name, digest in expected.items()
    ):
        raise ValueError("invalid expected-file manifest")
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("bundle must be a local directory, not a symlink")
    if {p.name for p in directory.iterdir()} != set(expected):
        raise ValueError("bundle contains missing or unexpected files")
    verified = {}
    for name, digest in expected.items():
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"bundle entry must be a regular file: {name}")
        with path.open("rb") as handle:
            actual = hashlib.file_digest(handle, "sha256").hexdigest()
        if actual != digest:
            raise ValueError(f"artifact hash mismatch: {name}")
        verified[name] = actual
    return verified


def validate_qwen_architecture(raw: object, spec: LocalEngineeringConfig) -> int:
    """Validate pinned architecture declarations; this does not inspect instantiated modules."""
    if not isinstance(raw, dict):
        raise ValueError("model config must be a mapping")
    required = {
        "model_type": "qwen3",
        "architectures": ["Qwen3ForCausalLM"],
        "num_hidden_layers": spec.site.layer_count,
        "hidden_size": spec.site.hidden_size,
        "vocab_size": 151936,
    }
    if any(
        type(raw.get(key)) is not type(value) or raw[key] != value
        for key, value in required.items()
    ):
        raise ValueError("model architecture differs from pinned local protocol")
    if not 0 <= spec.site.layer_index < raw["num_hidden_layers"]:
        raise ValueError("selected block is outside the model")
    return raw["vocab_size"]


@dataclass(frozen=True)
class PreparedTokenizer:
    tokenizer: DecisionTokenizer
    layout: AdapterLayout
    verified_files: dict[str, str]


def prepare_qwen_tokenizer(directory: Path, spec: LocalEngineeringConfig) -> PreparedTokenizer:
    """Load only verified tokenizer files, with network access and custom code disabled.

    The returned layout verifies metadata, not weight provenance or actual model structure.
    It must not be used as an execution-authorization token.
    """
    verified = verify_file_bundle(directory, TOKENIZER_FILES)
    raw = json.loads((directory / "config.json").read_text(encoding="utf-8"))
    vocabulary_size = validate_qwen_architecture(raw, spec)
    # Import only after file validation, so malformed bundles fail before library loading.
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        str(directory.resolve()),
        local_files_only=True,
        trust_remote_code=False,
    )
    if not isinstance(tokenizer.chat_template, str):
        raise ValueError("expected one explicit chat template")
    if hashlib.sha256(tokenizer.chat_template.encode()).hexdigest() != spec.input.template_sha256:
        raise ValueError("loaded tokenizer template differs from recorded template")
    for label, expected_id in [
        (spec.input.option_a, spec.input.option_a_id),
        (spec.input.option_b, spec.input.option_b_id),
    ]:
        if tokenizer.encode(label, add_special_tokens=False) != [expected_id]:
            raise ValueError("loaded answer token differs from recorded token")
    if tokenizer.pad_token_id != 151643 or len(tokenizer) > vocabulary_size:
        raise ValueError("loaded tokenizer vocabulary or padding declaration differs")
    return PreparedTokenizer(
        tokenizer=cast(DecisionTokenizer, tokenizer),
        layout=AdapterLayout(
            site=spec.site.activation_site(),
            hidden_size=spec.site.hidden_size,
            vocabulary_size=vocabulary_size,
            pad_token_id=tokenizer.pad_token_id,
            option_ids=(spec.input.option_a_id, spec.input.option_b_id),
            template_sha256=spec.input.template_sha256,
            revision=spec.model.revision,
        ),
        verified_files=verified,
    )
