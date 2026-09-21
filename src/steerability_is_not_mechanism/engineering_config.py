"""Versioned, non-executable local measurement specification (P1-005 through P1-008).

Loading this file validates declarations only: it never imports Transformers, fetches files,
sets runtime flags or instantiates a model. Runtime identity checks remain adapter obligations.
"""

from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .activations import ActivationSite


class Specification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class EngineeringModel(Specification):
    model_id: Literal["Qwen/Qwen3-0.6B"]
    revision: Literal["c1899de289a04d12100db370d81485cdf75e47ca"]
    tokenizer_revision: Literal["c1899de289a04d12100db370d81485cdf75e47ca"]
    dtype: Literal["float32"]
    device: Literal["auto", "mps", "cpu"]
    device_order: Literal["mps_then_cpu_separate_run"]
    allow_download: Literal[False]
    trust_remote_code: Literal[False]


class EngineeringInput(Specification):
    template_sha256: Literal["a55ee1b1660128b7098723e0abcd92caa0788061051c62d51cbe87d9cf1974d8"]
    message_layout: Literal["single_user_no_system_no_tools"]
    add_generation_prompt: Literal[True]
    enable_thinking: Literal[False]
    return_dict: Literal[False]
    add_special_tokens_on_rendered_text: Literal[False]
    option_a: Literal["A"]
    option_b: Literal["B"]
    option_a_id: Literal[32]
    option_b_id: Literal[33]
    batch_size: Literal[1]
    padding: Literal[False]


class EngineeringSite(Specification):
    layer_index: Literal[13]
    layer_count: Literal[28]
    hidden_size: Literal[1024]
    boundary: Literal["block_output_after_residual_additions_before_downstream_norm"]
    indexing: Literal["zero_based"]
    token_position: Literal["final_nonpadding_formatted_input_token"]

    def activation_site(self) -> ActivationSite:
        return ActivationSite(layer_index=self.layer_index)


class EngineeringRuntime(Specification):
    attention_implementation: Literal["eager"]
    evaluation_mode: Literal[True]
    inference_mode: Literal[True]
    use_cache: Literal[False]
    sampling: Literal[False]
    compile: Literal[False]
    external_kernels: Literal[False]
    mixed_precision: Literal[False]
    deterministic_algorithms: Literal[True]
    warn_only: Literal[False]
    seed: Literal[1729]
    cpu_intraop_threads: Literal[1]
    cpu_interop_threads: Literal[1]


class EngineeringChecks(Specification):
    baseline_repetitions: Literal[3]
    element_atol: float = Field(gt=0, allow_inf_nan=False)
    element_rtol: float = Field(gt=0, allow_inf_nan=False)
    margin_atol: float = Field(gt=0, allow_inf_nan=False)
    geometry_scaled_atol: float = Field(gt=0, allow_inf_nan=False)
    reference_dtype: Literal["cpu_float64"]
    comparison_scope: Literal["same_device_same_environment"]
    require_finite: Literal[True]
    record_exact_equality: Literal[True]
    unedited_positions_exact: Literal[True]

    @model_validator(mode="after")
    def keep_recorded_tolerances(self) -> Self:
        actual = (self.element_atol, self.element_rtol, self.margin_atol, self.geometry_scaled_atol)
        if actual != (1e-5, 1e-5, 1e-4, 1e-5):
            raise ValueError("p1-local-v1 tolerances must match the recorded P1-007 protocol")
        return self


class LocalEngineeringConfig(Specification):
    protocol_id: Literal["p1-local-v1"]
    status: Literal["specified_unverified"]
    synthetic_only: Literal[True]
    execution_enabled: Literal[False]
    model: EngineeringModel
    input: EngineeringInput
    site: EngineeringSite
    runtime: EngineeringRuntime
    checks: EngineeringChecks


def load_engineering_config(path: Path) -> LocalEngineeringConfig:
    """Validate a specification without changing runtime state or enabling execution."""
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ValueError("engineering specification root must be a mapping")
    return LocalEngineeringConfig.model_validate(raw)
