"""Weight-free protocol integrity and execution-guard regression checks."""

from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from steerability_is_not_mechanism.activations import ActivationSite
from steerability_is_not_mechanism.engineering_config import (
    LocalEngineeringConfig,
    load_engineering_config,
)
from steerability_is_not_mechanism.main import main
from steerability_is_not_mechanism.model_adapters import ModelLoadingDeferred, load_qwen_adapter

SPEC = Path("configs/local_model_engineering.yaml")


def test_repository_spec_loads_without_enabling_model_execution() -> None:
    config = load_engineering_config(SPEC)
    assert config.site.activation_site() == ActivationSite(layer_index=13)
    assert config.model.revision == config.model.tokenizer_revision
    assert not config.execution_enabled
    with pytest.raises(ModelLoadingDeferred):
        load_qwen_adapter()


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        (None, "execution_enabled", True),
        (None, "synthetic_only", False),
        ("model", "allow_download", True),
        ("model", "trust_remote_code", True),
        ("model", "device", "cuda"),
        ("model", "dtype", "float16"),
        ("model", "revision", "main"),
        ("model", "tokenizer_revision", "0" * 40),
        ("input", "template_sha256", "0" * 64),
        ("input", "enable_thinking", True),
        ("input", "option_a_id", 362),
        ("input", "padding", True),
        ("site", "layer_index", 14),
        ("site", "boundary", "block_input"),
        ("runtime", "warn_only", True),
        ("runtime", "use_cache", True),
        ("checks", "element_atol", 0.001),
        ("checks", "margin_atol", float("nan")),
    ],
)
def test_incompatible_protocol_is_rejected(section: str | None, field: str, value: object) -> None:
    raw = load_engineering_config(SPEC).model_dump()
    target = raw if section is None else raw[section]
    target[field] = value
    with pytest.raises(ValidationError):
        LocalEngineeringConfig.model_validate(raw)


@pytest.mark.parametrize("section", [None, "model", "input", "site", "runtime", "checks"])
def test_protocol_fields_cannot_be_silently_omitted(section: str | None) -> None:
    original = load_engineering_config(SPEC).model_dump()
    fields = original if section is None else original[section]
    for field in fields:
        raw = load_engineering_config(SPEC).model_dump()
        target = raw if section is None else raw[section]
        del target[field]
        with pytest.raises(ValidationError):
            LocalEngineeringConfig.model_validate(raw)


def test_unknown_setting_and_post_validation_mutation_are_rejected() -> None:
    config = load_engineering_config(SPEC)
    raw = config.model_dump()
    raw["runtime"]["silently_fallback"] = True
    with pytest.raises(ValidationError):
        LocalEngineeringConfig.model_validate(raw)
    with pytest.raises(ValidationError, match="frozen"):
        config.model.device = "cpu"


@pytest.mark.parametrize("layer_index", [-1, True])
def test_activation_site_rejects_invalid_index(layer_index: int) -> None:
    with pytest.raises(ValueError, match="zero-based"):
        ActivationSite(layer_index=layer_index)


def test_cli_model_guard_remains_closed(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("sys.argv", ["sim-smoke", "--config", "configs/local_smoke.yaml", "--with-model"]):
        with pytest.raises(SystemExit) as error:
            main()
    assert error.value.code == 2
    assert "model-backed execution is guarded" in capsys.readouterr().err
