"""Подсистема происхождения данных.

Построитель lineage обходит репозиторий метаданных и формирует
нормализованный ``LineageGraph`` с рёбрами уровня датасета и колонок.
Затем граф публикуется в OpenMetadata через официальный SDK или
выгружается в формате OpenLineage для офлайн-каталогов.
"""

from .builder import ColumnEdge, DatasetEdge, LineageBuilder, LineageGraph
from .openlineage_export import OpenLineageExporter
from .openmetadata import OpenMetadataPublisher

__all__ = [
    "ColumnEdge",
    "DatasetEdge",
    "LineageBuilder",
    "LineageGraph",
    "OpenLineageExporter",
    "OpenMetadataPublisher",
]
