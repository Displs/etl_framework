"""Active-metadata model.

The model is intentionally split across multiple modules so that each concept
(source, target, mapping, strategy, schedule) can evolve independently and so
that error messages from Pydantic point to a meaningful location.
"""

from .entity import AuditSpec, EntityMetadata, EntitySource, EntitySpec
from .enums import ExtractMode, Layer, LoadStrategy, SinkKind, SourceKind, TableFormat
from .mapping import ColumnMapping
from .schedule import ScheduleSpec
from .source import ExtractSpec, SourceConnection, SourceSpec, SourceTable
from .strategy import FullLoad, IncrementalLoad, LoadSpec, SCD1Load, SCD2Load
from .target import SinkTable, TargetTable

__all__ = [
    "AuditSpec",
    "ColumnMapping",
    "EntityMetadata",
    "EntitySource",
    "EntitySpec",
    "ExtractMode",
    "ExtractSpec",
    "FullLoad",
    "IncrementalLoad",
    "Layer",
    "LoadSpec",
    "LoadStrategy",
    "SCD1Load",
    "SCD2Load",
    "ScheduleSpec",
    "SinkKind",
    "SinkTable",
    "SourceConnection",
    "SourceKind",
    "SourceSpec",
    "SourceTable",
    "TableFormat",
    "TargetTable",
]
