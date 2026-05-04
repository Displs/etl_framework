"""Source-system specifications.

A SourceSpec describes how to connect to a source system and how to extract a
specific table. SourceSpecs are stored as separate YAML files and referenced
from EntitySpec via dotted ``source_ref`` like ``postgres_oltp.public.clients``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .enums import ExtractMode, SourceKind


class SourceConnection(BaseModel):
    """Connection parameters for a source system.

    Sensitive fields are stored as references resolved at runtime by
    :mod:`etl_framework.security.secrets` (e.g. ``env:PG_PASSWORD``).
    """

    model_config = ConfigDict(extra="forbid")

    kind: SourceKind
    host: str
    port: int
    database: str
    user: str = Field(description="Plain user or secret reference")
    password: str = Field(description="Secret reference, e.g. env:PG_PASSWORD")
    jdbc_options: dict[str, str] = Field(default_factory=dict)


class ExtractSpec(BaseModel):
    """How to read data from the source."""

    model_config = ConfigDict(extra="forbid")

    mode: ExtractMode = ExtractMode.FULL
    watermark_column: str | None = Field(
        default=None,
        description="Column used to filter incremental slices; required for INCREMENTAL mode",
    )
    cdc_slot: str | None = Field(
        default=None,
        description="Logical replication slot name; required for CDC mode",
    )
    fetch_size: int = 10_000


class SourceTable(BaseModel):
    """Logical pointer to a source table."""

    model_config = ConfigDict(extra="forbid")

    schema_: str = Field(alias="schema")
    table: str
    extract: ExtractSpec = Field(default_factory=ExtractSpec)


class SourceSpec(BaseModel):
    """Top-level source specification, stored as a YAML document."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    description: str | None = None
    connection: SourceConnection
