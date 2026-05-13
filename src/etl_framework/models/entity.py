"""Спецификация сущности верхнего уровня — единица активных метаданных."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import Layer, LoadStrategy
from .mapping import ColumnMapping
from .schedule import ScheduleSpec
from .strategy import LoadSpec
from .target import SinkTable, TargetTable


class AuditSpec(BaseModel):
    """Технические колонки аудита, добавляемые к каждой загруженной записи."""

    model_config = ConfigDict(extra="forbid")

    load_ts_column: str = "load_ts"
    source_system_column: str = "source_system"
    record_hash_column: str | None = "record_hash"
    surrogate_key_column: str | None = None


class EntitySource(BaseModel):
    """Ссылка из сущности на таблицу источника."""

    model_config = ConfigDict(extra="forbid")

    ref: str = Field(
        description="Точечная ссылка 'имя_источника.схема.таблица'",
        pattern=r"^[a-z0-9_]+(\.[a-z0-9_]+){2}$",
    )

    @property
    def source_name(self) -> str:
        return self.ref.split(".", 1)[0]

    @property
    def schema_(self) -> str:
        return self.ref.split(".")[1]

    @property
    def table(self) -> str:
        return self.ref.split(".")[2]


class EntityMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    layer: Layer
    description: str | None = None
    owner: str | None = None
    tags: list[str] = Field(default_factory=list)


class EntitySpec(BaseModel):
    """Спецификация активных метаданных одного ETL-процесса.

    Один YAML-документ соответствует одной ``EntitySpec`` и порождает
    одну задачу Airflow и одно PySpark-приложение при кодогенерации.
    """

    model_config = ConfigDict(extra="forbid")

    api_version: str = Field(default="etlf/v1", alias="apiVersion")
    kind: str = Field(default="Entity")
    metadata: EntityMetadata
    source: EntitySource
    target: TargetTable
    load: LoadSpec
    mapping: list[ColumnMapping] = Field(min_length=1)
    audit: AuditSpec = Field(default_factory=AuditSpec)
    schedule: ScheduleSpec = Field(default_factory=ScheduleSpec)
    sinks: list[SinkTable] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_kind(self) -> EntitySpec:
        if self.kind != "Entity":
            raise ValueError(f"неподдерживаемый kind '{self.kind}'; ожидался 'Entity'")
        return self

    @model_validator(mode="after")
    def _check_target_columns_unique(self) -> EntitySpec:
        seen: set[str] = set()
        for col in self.mapping:
            if col.target in seen:
                raise ValueError(f"дубликат целевой колонки '{col.target}'")
            seen.add(col.target)
        return self

    @model_validator(mode="after")
    def _check_strategy_columns(self) -> EntitySpec:
        targets = {col.target for col in self.mapping}
        bk = getattr(self.load, "business_keys", None)
        if bk is not None:
            missing = [k for k in bk if k not in targets]
            if missing:
                raise ValueError(
                    f"business_keys ссылается на неизвестные целевые колонки: {missing}"
                )
        tracked = getattr(self.load, "tracked_columns", None)
        if tracked:
            missing = [c for c in tracked if c not in targets]
            if missing:
                raise ValueError(
                    f"tracked_columns ссылается на неизвестные целевые колонки: {missing}"
                )
        if self.load.strategy == LoadStrategy.SCD2:
            for fld in ("effective_from", "effective_to", "current_flag"):
                if getattr(self.load, fld) in targets:
                    raise ValueError(
                        f"техническая колонка SCD2 '{getattr(self.load, fld)}' "
                        "не должна присутствовать в mapping (она генерируется автоматически)"
                    )
        return self

    @property
    def primary_keys(self) -> list[str]:
        bk = getattr(self.load, "business_keys", None)
        if bk:
            return list(bk)
        return [col.target for col in self.mapping if col.pk]
