"""Automatic metadata extraction from source systems.

The discovery layer reads physical schema information from a source system and
emits a *spec stub* — a partially populated EntitySpec that the data engineer
then enriches with mapping rules, load strategy and schedule. Stubs are
deliberately conservative: every column becomes a direct copy with the same
type, and no transforms are inferred.
"""

from .postgres import PostgresDiscoverer, discover_table

__all__ = ["PostgresDiscoverer", "discover_table"]
