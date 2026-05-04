"""Data-lineage subsystem.

The lineage builder walks the metadata repository and produces a normalized
``LineageGraph`` containing dataset-level and column-level edges. The graph is
then published to OpenMetadata via the official SDK (or exported as
OpenLineage JSON for offline catalogs).
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
