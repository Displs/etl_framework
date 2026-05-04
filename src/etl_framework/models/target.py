"""Target table specifications."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .enums import TableFormat


class TargetTable(BaseModel):
    """Where to write the data.

    The catalog/schema/table triple identifies the table in the Spark/Iceberg
    catalog. The framework does not create the catalog itself — it must already
    exist in the Spark configuration.
    """

    model_config = ConfigDict(extra="forbid")

    catalog: str = "warehouse"
    schema_: str = Field(alias="schema")
    table: str
    format: TableFormat = TableFormat.ICEBERG
    location: str | None = Field(
        default=None,
        description="Optional explicit location URI (s3a://bucket/path) for non-managed tables",
    )
    partition_by: list[str] = Field(default_factory=list)
    properties: dict[str, str] = Field(
        default_factory=dict,
        description="Iceberg table properties, e.g. write.format.default=orc",
    )

    @property
    def fqn(self) -> str:
        return f"{self.catalog}.{self.schema_}.{self.table}"


class SinkTable(BaseModel):
    """External downstream sink (Greenplum/ClickHouse mart export)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    kind: str = Field(pattern=r"^(greenplum|clickhouse)$")
    jdbc_url: str
    schema_: str = Field(alias="schema")
    table: str
    user: str
    password: str
    write_mode: str = Field(default="overwrite", pattern=r"^(overwrite|append)$")
