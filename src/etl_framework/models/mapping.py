"""Правила маппинга колонок.

``ColumnMapping`` описывает, как формируется одна колонка целевой таблицы
из одной или нескольких колонок источника. Поддерживается три формы:

* прямой перенос (``source`` задан, ``transform`` и ``expression`` пусты);
* скалярное преобразование одной исходной колонки (``transform`` — фрагмент
  Spark SQL; символ ``$`` подставляется именем исходной колонки);
* свободное выражение над несколькими исходными колонками (``expression`` —
  выражение Spark SQL, вычисляемое над DataFrame источника).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ColumnMapping(BaseModel):
    """Правило формирования одной целевой колонки."""

    model_config = ConfigDict(extra="forbid")

    target: str = Field(pattern=r"^[a-z_][a-z0-9_]*$")
    type: str = Field(description="Тип целевой колонки в Spark/SQL, например BIGINT или VARCHAR(120)")
    source: str | None = Field(
        default=None,
        description="Имя исходной колонки для прямого переноса или скалярного transform",
    )
    transform: str | None = Field(
        default=None,
        description="Преобразование одной колонки; символ '$' заменяется именем источника",
    )
    expression: str | None = Field(
        default=None,
        description="Свободное Spark SQL-выражение для производных колонок из нескольких источников",
    )
    null_default: str | None = Field(
        default=None, description="SQL-литерал, подставляемый вместо NULL"
    )
    pk: bool = Field(default=False, description="Входит в технический первичный ключ")
    description: str | None = None

    @model_validator(mode="after")
    def _check_consistency(self) -> ColumnMapping:
        if self.expression is not None:
            if self.source or self.transform:
                raise ValueError(
                    f"колонка '{self.target}': 'expression' взаимоисключающа с "
                    "'source' и 'transform'"
                )
        else:
            if not self.source:
                raise ValueError(
                    f"колонка '{self.target}': должно быть задано 'source' или 'expression'"
                )
        return self

    def render_expression(self) -> str:
        """Вернуть фрагмент Spark SQL, формирующий значение целевой колонки."""
        if self.expression is not None:
            expr = self.expression
        elif self.transform is not None:
            assert self.source is not None  # гарантировано валидатором
            expr = self.transform.replace("$", self.source)
        else:
            assert self.source is not None
            expr = self.source

        if self.null_default is not None:
            expr = f"coalesce({expr}, {self.null_default})"
        return f"cast({expr} as {self.type})"

    def source_columns(self) -> list[str]:
        """Вернуть список исходных колонок, на которые опирается маппинг.

        Используется построителем lineage. Для свободных ``expression`` в v0.1
        возвращаем пустой список — статический разбор SQL вне области текущей
        версии; в будущих версиях разработчик сможет аннотировать ``expression``
        явным полем ``lineage_sources``.
        """
        if self.source is not None:
            return [self.source]
        return []
