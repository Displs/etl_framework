"""Спецификации систем-источников.

``SourceSpec`` описывает, как подключиться к системе-источнику и как
извлечь конкретную таблицу. Каждый ``SourceSpec`` хранится в отдельном
YAML-файле и упоминается из ``EntitySpec`` через точечную ссылку
``source_ref`` вида ``postgres_oltp.public.clients``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .enums import ExtractMode, SourceKind


class SourceConnection(BaseModel):
    """Параметры подключения к системе-источнику.

    Чувствительные поля хранятся как ссылки на секреты, разрешаемые
    в runtime через :mod:`etl_framework.security.secrets`
    (например, ``env:PG_PASSWORD``).
    """

    model_config = ConfigDict(extra="forbid")

    kind: SourceKind
    host: str
    port: int
    database: str
    user: str = Field(description="Логин или ссылка на секрет")
    password: str = Field(description="Ссылка на секрет, например env:PG_PASSWORD")
    jdbc_options: dict[str, str] = Field(default_factory=dict)


class ExtractSpec(BaseModel):
    """Параметры извлечения из источника."""

    model_config = ConfigDict(extra="forbid")

    mode: ExtractMode = ExtractMode.FULL
    watermark_column: str | None = Field(
        default=None,
        description="Колонка-маркер для инкрементальной выборки; обязательна для режима INCREMENTAL",
    )
    cdc_slot: str | None = Field(
        default=None,
        description="Имя слота логической репликации; обязательно для режима CDC",
    )
    fetch_size: int = 10_000


class SourceTable(BaseModel):
    """Логический указатель на таблицу источника."""

    model_config = ConfigDict(extra="forbid")

    schema_: str = Field(alias="schema")
    table: str
    extract: ExtractSpec = Field(default_factory=ExtractSpec)


class SourceSpec(BaseModel):
    """Спецификация источника верхнего уровня, хранимая как YAML-документ."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    description: str | None = None
    connection: SourceConnection
