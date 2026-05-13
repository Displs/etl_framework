"""Спецификации целевых таблиц."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .enums import TableFormat


class TargetTable(BaseModel):
    """Куда писать данные.

    Тройка catalog/schema/table идентифицирует таблицу в каталоге
    Spark/Iceberg. Сам каталог фреймворком не создаётся — он должен быть
    предварительно зарегистрирован в конфигурации Spark.
    """

    model_config = ConfigDict(extra="forbid")

    catalog: str = "warehouse"
    schema_: str = Field(alias="schema")
    table: str
    format: TableFormat = TableFormat.ICEBERG
    location: str | None = Field(
        default=None,
        description="Явный URI размещения (s3a://bucket/path) для unmanaged-таблиц",
    )
    partition_by: list[str] = Field(default_factory=list)
    properties: dict[str, str] = Field(
        default_factory=dict,
        description="Свойства Iceberg-таблицы, например write.format.default=orc",
    )

    @property
    def fqn(self) -> str:
        return f"{self.catalog}.{self.schema_}.{self.table}"


class SinkTable(BaseModel):
    """Внешний приёмник для экспорта витрин (Greenplum/ClickHouse)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    kind: str = Field(pattern=r"^(greenplum|clickhouse)$")
    jdbc_url: str
    schema_: str = Field(alias="schema")
    table: str
    user: str
    password: str
    write_mode: str = Field(default="overwrite", pattern=r"^(overwrite|append)$")
