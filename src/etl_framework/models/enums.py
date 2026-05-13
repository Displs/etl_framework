"""Перечисления, используемые в модели метаданных."""

from enum import Enum


class Layer(str, Enum):
    """Логический слой корпоративного хранилища данных."""

    STG = "stg"
    ODS = "ods"
    DDS = "dds"
    DM = "dm"


class LoadStrategy(str, Enum):
    """Поддерживаемые паттерны загрузки."""

    FULL = "full"
    INCREMENTAL = "incremental"
    SCD1 = "scd1"
    SCD2 = "scd2"


class ExtractMode(str, Enum):
    """Режим извлечения из источника."""

    FULL = "full"
    INCREMENTAL = "incremental"
    CDC = "cdc"


class TableFormat(str, Enum):
    """Формат физического хранения целевой таблицы."""

    ICEBERG = "iceberg"
    PARQUET = "parquet"
    ORC = "orc"


class SourceKind(str, Enum):
    """Тип системы-источника."""

    POSTGRES = "postgres"
    GREENPLUM = "greenplum"
    CLICKHOUSE = "clickhouse"
    FILE = "file"


class SinkKind(str, Enum):
    """Тип внешнего приёмника для экспорта витрин."""

    GREENPLUM = "greenplum"
    CLICKHOUSE = "clickhouse"
