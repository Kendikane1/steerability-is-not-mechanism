"""Weight-free file validation tests; all temporary artifacts are synthetic."""

import hashlib
from pathlib import Path

import pytest

from steerability_is_not_mechanism.engineering_config import load_engineering_config
from steerability_is_not_mechanism.qwen_preflight import (
    prepare_qwen_tokenizer,
    validate_qwen_architecture,
    verify_file_bundle,
)


@pytest.fixture
def bundle(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    contents = b"SYNTHETIC artifact, not Qwen"
    (tmp_path / "fixture.txt").write_bytes(contents)
    return tmp_path, {"fixture.txt": hashlib.sha256(contents).hexdigest()}


def test_matching_bundle_passes(bundle: tuple[Path, dict[str, str]]):
    directory, expected = bundle
    assert verify_file_bundle(directory, expected) == expected


@pytest.mark.parametrize("mutation", ["modified", "missing", "extra", "symlink", "directory"])
def test_changed_bundles_fail(bundle: tuple[Path, dict[str, str]], mutation: str):
    directory, expected = bundle
    file = directory / "fixture.txt"
    if mutation == "modified":
        file.write_text("different")
    elif mutation == "missing":
        file.unlink()
    elif mutation == "extra":
        (directory / "chat_template.jinja").write_text("unexpected override")
    elif mutation == "symlink":
        file.unlink()
        file.symlink_to("missing-target")
    else:
        file.unlink()
        file.mkdir()
    with pytest.raises(ValueError):
        verify_file_bundle(directory, expected)


@pytest.mark.parametrize("name", ["../outside", "a/b", "a\\b", ".", ""])
def test_manifest_cannot_escape_bundle(tmp_path: Path, name: str):
    with pytest.raises(ValueError, match="manifest"):
        verify_file_bundle(tmp_path, {name: "0" * 64})


def test_synthetic_bundle_cannot_be_loaded_as_qwen(bundle: tuple[Path, dict[str, str]]):
    directory, _ = bundle
    spec = load_engineering_config(Path("configs/local_model_engineering.yaml"))
    with pytest.raises(ValueError, match="missing or unexpected"):
        prepare_qwen_tokenizer(directory, spec)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("model_type", "llama"),
        ("architectures", ["Other"]),
        ("num_hidden_layers", 27),
        ("hidden_size", 2048),
        ("vocab_size", 128),
    ],
)
def test_wrong_architecture_rejected(key: str, value: object):
    spec = load_engineering_config(Path("configs/local_model_engineering.yaml"))
    raw: dict[str, object] = {
        "model_type": "qwen3",
        "architectures": ["Qwen3ForCausalLM"],
        "num_hidden_layers": 28,
        "hidden_size": 1024,
        "vocab_size": 151936,
    }
    assert validate_qwen_architecture(raw, spec) == 151936
    raw[key] = value
    with pytest.raises(ValueError, match="architecture"):
        validate_qwen_architecture(raw, spec)
