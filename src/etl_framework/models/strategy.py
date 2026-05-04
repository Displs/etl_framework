"""Load-strategy descriptors.

Each load strategy is represented by its own model so that required parameters
(e.g. business keys for SCD2) are checked statically by Pydantic instead of by
the codegen engine.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .enums import LoadStrategy


class _StrategyBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FullLoad(_StrategyBase):
    strategy: Literal[LoadStrategy.FULL] = LoadStrategy.FULL


class IncrementalLoad(_StrategyBase):
    strategy: Literal[LoadStrategy.INCREMENTAL] = LoadStrategy.INCREMENTAL
    business_keys: list[str] = Field(min_length=1)
    watermark_column: str = Field(
        description="Target-side watermark column used to compute the next load offset"
    )


class SCD1Load(_StrategyBase):
    strategy: Literal[LoadStrategy.SCD1] = LoadStrategy.SCD1
    business_keys: list[str] = Field(min_length=1)
    tracked_columns: list[str] = Field(
        default_factory=list,
        description="Columns whose changes trigger an update; empty means all non-key cols",
    )


class SCD2Load(_StrategyBase):
    strategy: Literal[LoadStrategy.SCD2] = LoadStrategy.SCD2
    business_keys: list[str] = Field(min_length=1)
    tracked_columns: list[str] = Field(min_length=1)
    effective_from: str = "valid_from"
    effective_to: str = "valid_to"
    current_flag: str = "is_current"
    end_of_time: str = Field(
        default="9999-12-31",
        description="Sentinel value used to mark currently-active versions",
    )


LoadSpec = Annotated[
    FullLoad | IncrementalLoad | SCD1Load | SCD2Load,
    Field(discriminator="strategy"),
]
