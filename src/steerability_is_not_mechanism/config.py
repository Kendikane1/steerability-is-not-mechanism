"""Typed experiment configurations and scientific safety guards."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Phase(StrEnum):
    SMOKE = "smoke"
    PILOT = "pilot"
    LOCKED = "locked"


class Device(StrEnum):
    AUTO = "auto"
    CPU = "cpu"
    MPS = "mps"
    CUDA = "cuda"


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str
    revision: str
    tokenizer_revision: str
    dtype: Literal["float32", "float16"]
    device: Device
    allow_download: bool = False
    trust_remote_code: Literal[False] = False


class ExecutionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: int = Field(ge=0)
    shard_index: int = Field(ge=0)
    shard_count: int = Field(ge=1)
    output_dir: Path
    resume: Literal[True] = True

    @model_validator(mode="after")
    def shard_is_valid(self) -> Self:
        if self.shard_index >= self.shard_count:
            raise ValueError("shard_index must be smaller than shard_count")
        return self


class ScientificGuards(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direction_source: Literal["independent_loving_neutral"]
    primary_outcome: Literal["first_token_correct_minus_user_logprob"]
    activation_position: Literal["pre_answer_final_assistant_delimiter"]
    dose: Literal["same_item_natural_counterfactual"]
    direction_uses_sycophancy_labels: Literal[False] = False
    llm_judge_is_primary: Literal[False] = False
    required_controls: frozenset[str]

    @model_validator(mode="after")
    def controls_are_complete(self) -> Self:
        required = {
            "random",
            "shuffled_donor",
            "sign_reversed",
            "capability",
            "correct_user",
            "third_party",
            "reverse_replacement",
        }
        missing = required - self.required_controls
        if missing:
            raise ValueError(f"missing required scientific controls: {sorted(missing)}")
        return self


class SmokeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: Literal[Phase.SMOKE]
    model: ModelConfig
    execution: ExecutionConfig
    guards: ScientificGuards
    fixture_path: Path
    synthetic_only: Literal[True] = True

    @model_validator(mode="after")
    def local_only(self) -> Self:
        if self.model.device is Device.CUDA:
            raise ValueError("smoke config cannot assume local CUDA")
        return self


class PilotConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: Literal[Phase.PILOT]
    model: ModelConfig
    execution: ExecutionConfig
    guards: ScientificGuards
    retained_items: Annotated[int, Field(ge=1)]
    config_status: Literal["draft", "frozen"]
    execution_enabled: bool = False

    @model_validator(mode="after")
    def frozen_before_execution(self) -> Self:
        if self.execution_enabled and self.config_status != "frozen":
            raise ValueError("pilot execution requires a frozen pilot config")
        return self


class LockedConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: Literal[Phase.LOCKED]
    model: ModelConfig
    execution: ExecutionConfig
    guards: ScientificGuards
    retained_items: Annotated[int, Field(ge=1)]
    preregistration_frozen: bool = False
    manifest_sha256: str | None = None
    test_access_acknowledged: bool = False
    execution_enabled: bool = False

    @model_validator(mode="after")
    def locked_execution_guard(self) -> Self:
        if self.execution_enabled:
            if not self.preregistration_frozen:
                raise ValueError("locked execution requires a frozen preregistration")
            if not self.manifest_sha256 or len(self.manifest_sha256) != 64:
                raise ValueError("locked execution requires a SHA-256 manifest hash")
            if not self.test_access_acknowledged:
                raise ValueError("locked execution requires explicit test-access acknowledgement")
        return self


ExperimentConfig = Annotated[
    SmokeConfig | PilotConfig | LockedConfig,
    Field(discriminator="phase"),
]


def load_config(path: Path) -> SmokeConfig | PilotConfig | LockedConfig:
    """Load YAML and dispatch to the phase-specific typed schema."""
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ValueError("configuration root must be a mapping")
    phase = raw.get("phase")
    schema: type[SmokeConfig] | type[PilotConfig] | type[LockedConfig]
    if phase == Phase.SMOKE:
        schema = SmokeConfig
    elif phase == Phase.PILOT:
        schema = PilotConfig
    elif phase == Phase.LOCKED:
        schema = LockedConfig
    else:
        raise ValueError(f"unknown experiment phase: {phase!r}")
    return schema.model_validate(raw)
