from pathlib import Path

import pytest

from steerability_is_not_mechanism.config import SmokeConfig, load_config
from steerability_is_not_mechanism.main import synthetic_smoke


def test_synthetic_smoke_runs_end_to_end() -> None:
    config = load_config(Path("configs/local_smoke.yaml"))
    assert isinstance(config, SmokeConfig)

    result = synthetic_smoke(config)

    assert result["config_phase"] == "smoke"
    assert result["direction_validation_accuracy"] == pytest.approx(1.0)
    assert result["rescued_coordinate"] == pytest.approx(1.0)
    assert result["induced_coordinate"] == pytest.approx(4.0)
    assert result["answer_margin"] == pytest.approx(1.5)
