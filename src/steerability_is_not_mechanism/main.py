"""Phase-aware command line entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .config import SmokeConfig, load_config
from .directions import estimate_mean_difference, pairwise_direction_accuracy
from .interventions import paired_natural_replacements
from .metrics import answer_margin


def synthetic_smoke(config: SmokeConfig) -> dict[str, float | str]:
    with config.fixture_path.open(encoding="utf-8") as handle:
        fixture = json.load(handle)
    loving = np.asarray(fixture["loving_activations"], dtype=np.float64)
    neutral = np.asarray(fixture["neutral_activations"], dtype=np.float64)
    direction = estimate_mean_difference(loving[:2], neutral[:2])
    validation_accuracy = pairwise_direction_accuracy(direction, loving[2:], neutral[2:])
    pressured = np.asarray(fixture["pressured_activation"], dtype=np.float64)
    low = np.asarray(fixture["low_activation"], dtype=np.float64)
    rescued, induced = paired_natural_replacements(pressured, low, direction)
    margin = answer_margin(np.asarray(fixture["logits"]), 0, 1)
    return {
        "config_phase": config.phase.value,
        "direction_validation_accuracy": validation_accuracy,
        "rescued_coordinate": float(direction @ rescued),
        "induced_coordinate": float(direction @ induced),
        "answer_margin": margin,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--with-model", action="store_true")
    arguments = parser.parse_args()
    config = load_config(arguments.config)
    if arguments.with_model:
        parser.error(
            "model-backed execution is guarded until Phase 1 decisions are frozen and the "
            "small-model download is explicitly authorized"
        )
    if not isinstance(config, SmokeConfig):
        parser.error("Phase 0 CLI executes only a smoke config")
    print(json.dumps(synthetic_smoke(config), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
