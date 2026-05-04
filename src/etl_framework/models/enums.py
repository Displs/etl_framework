"""Enumerations used across the metadata model."""

from enum import Enum


class Layer(str, Enum):
    """Logical layer of the corporate data warehouse."""

    STG = "stg"
    ODS = "ods"
    DDS = "dds"
    DM = "dm"


class LoadStrategy(str, Enum):
    """Supported load patterns."""

    FULL = "full"
    INCREMENTAL = "incremental"
    SCD1 = "scd1"
    SCD2 = "scd2"


class ExtractMode(str, Enum):
    """Source extraction mode."""

    FULL = "full"
    INCREMENTAL = "incremental"
    CDC = "cdc"


class TableFormat(str, Enum):
    """Physical storage format for the target table."""

    ICEBERG = "iceberg"
    PARQUET = "parquet"
    ORC = "orc"


class SourceKind(str, Enum):
    """Type of source system."""

    POSTGRES = "postgres"
    GREENPLUM = "greenplum"
    CLICKHOUSE = "clickhouse"
    FILE = "file"


class SinkKind(str, Enum):
    """Type of downstream sink for mart export."""

    GREENPLUM = "greenplum"
    CLICKHOUSE = "clickhouse"
