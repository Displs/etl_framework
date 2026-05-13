"""Модель активных метаданных.

Модель намеренно разделена на несколько модулей, чтобы каждое понятие
(источник, целевая таблица, маппинг, стратегия, расписание) могло
эволюционировать независимо, а сообщения об ошибках от Pydantic
указывали на осмысленное место.
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
