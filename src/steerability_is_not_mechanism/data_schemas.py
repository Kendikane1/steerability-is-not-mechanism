"""Schemas and deterministic family-level splitting."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Split(StrEnum):
    DIRECTION_EXTRACTION = "direction_extraction"
    DIRECTION_VALIDATION = "direction_validation"
    PILOT = "pilot"
    DEVELOPMENT = "development"
    LOCKED_TEST = "locked_test"


class DirectionPair(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pair_id: str
    family_id: str
    split: Split
    loving_text: str
    neutral_text: str
    synthetic: bool = False

    @model_validator(mode="after")
    def direction_split_only(self) -> DirectionPair:
        allowed = {Split.DIRECTION_EXTRACTION, Split.DIRECTION_VALIDATION}
        if self.split not in allowed:
            raise ValueError("direction pairs belong only to extraction or validation")
        if self.loving_text == self.neutral_text:
            raise ValueError("paired texts must differ")
        return self


class DecisionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    family_id: str
    split: Split
    question: str
    options: tuple[str, str]
    correct_index: int = Field(ge=0, le=1)
    user_endorsed_index: int = Field(ge=0, le=1)
    synthetic: bool = False

    @model_validator(mode="after")
    def objective_false_user_item(self) -> DecisionItem:
        allowed = {Split.PILOT, Split.DEVELOPMENT, Split.LOCKED_TEST}
        if self.split not in allowed:
            raise ValueError("decision items cannot enter direction splits")
        if self.correct_index == self.user_endorsed_index:
            raise ValueError("core decision item must encode a false user endorsement")
        if self.options[0] == self.options[1]:
            raise ValueError("binary options must differ")
        return self


def deterministic_family_split(
    family_ids: Sequence[str], seed: int, split_counts: Mapping[Split, int]
) -> dict[str, Split]:
    """Assign whole families reproducibly, independent of input ordering."""
    unique = set(family_ids)
    if len(unique) != len(family_ids):
        raise ValueError("family_ids must be unique")
    if sum(split_counts.values()) != len(family_ids):
        raise ValueError("split counts must sum to the number of families")
    if any(count < 0 for count in split_counts.values()):
        raise ValueError("split counts cannot be negative")

    ordered = sorted(
        family_ids,
        key=lambda family: hashlib.sha256(f"{seed}:{family}".encode()).hexdigest(),
    )
    assignment: dict[str, Split] = {}
    cursor = 0
    for split in sorted(split_counts, key=str):
        count = split_counts[split]
        for family in ordered[cursor : cursor + count]:
            assignment[family] = split
        cursor += count
    return assignment


def assert_disjoint_ids(groups: Mapping[str, set[str]]) -> None:
    """Fail if any identifier appears in more than one named group."""
    seen: dict[str, str] = {}
    for group, identifiers in groups.items():
        for identifier in identifiers:
            if identifier in seen:
                raise ValueError(f"{identifier!r} overlaps {seen[identifier]!r} and {group!r}")
            seen[identifier] = group
