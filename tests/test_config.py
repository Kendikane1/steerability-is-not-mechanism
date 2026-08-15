from pathlib import Path

import pytest
from pydantic import ValidationError

from steerability_is_not_mechanism.config import (
    LockedConfig,
    PilotConfig,
    SmokeConfig,
    load_config,
)


@pytest.mark.parametrize(
    ("path", "expected_type"),
    [
        ("configs/local_smoke.yaml", SmokeConfig),
        ("configs/pilot.yaml", PilotConfig),
        ("configs/locked_experiment.yaml", LockedConfig),
    ],
)
def test_repository_configs_validate(path: str, expected_type: type[object]) -> None:
    assert isinstance(load_config(Path(path)), expected_type)


def test_required_control_cannot_be_removed() -> None:
    config = load_config(Path("configs/local_smoke.yaml"))
    raw = config.model_dump(mode="json")
    raw["guards"]["required_controls"].remove("random")

    with pytest.raises(ValidationError, match="missing required scientific controls"):
        SmokeConfig.model_validate(raw)


def test_locked_execution_needs_freeze_hash_and_acknowledgement() -> None:
    config = load_config(Path("configs/locked_experiment.yaml"))
    raw = config.model_dump(mode="json")
    raw["execution_enabled"] = True

    with pytest.raises(ValidationError, match="frozen preregistration"):
        LockedConfig.model_validate(raw)
