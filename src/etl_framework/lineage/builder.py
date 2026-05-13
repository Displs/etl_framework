"""Построение графа происхождения данных по репозиторию метаданных.

Lineage выводится статически из ``ColumnMapping.source_columns()``.
Свободные ``expression``-маппинги в v0.1 не дают колоночных рёбер;
пользователь может уточнить lineage, заменив ``expression`` явным
правилом ``transform`` по одной колонке.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models import EntitySpec, SourceSpec
from ..repository import MetadataRepository


@dataclass(frozen=True)
class DatasetRef:
    """Логический идентификатор датасета — узел графа lineage."""

    namespace: str
    name: str

    @classmethod
    def from_target(cls, spec: EntitySpec) -> DatasetRef:
        return cls(
            namespace=f"iceberg://{spec.target.catalog}",
            name=f"{spec.target.schema_}.{spec.target.table}",
        )

    @classmethod
    def from_source(cls, source: SourceSpec, schema: str, table: str) -> DatasetRef:
        ns = (
            f"{source.connection.kind.value}://{source.connection.host}:"
            f"{source.connection.port}/{source.connection.database}"
        )
        return cls(namespace=ns, name=f"{schema}.{table}")

    def __str__(self) -> str:
        return f"{self.namespace}/{self.name}"


@dataclass(frozen=True)
class DatasetEdge:
    upstream: DatasetRef
    downstream: DatasetRef
    job: str  # имя сущности (entity)


@dataclass(frozen=True)
class ColumnEdge:
    upstream: DatasetRef
    upstream_column: str
    downstream: DatasetRef
    downstream_column: str
    job: str


@dataclass
class LineageGraph:
    datasets: set[DatasetRef] = field(default_factory=set)
    dataset_edges: list[DatasetEdge] = field(default_factory=list)
    column_edges: list[ColumnEdge] = field(default_factory=list)


class LineageBuilder:
    def build(self, repo: MetadataRepository) -> LineageGraph:
        graph = LineageGraph()
        for ent in repo.entities.values():
            src = repo.source(ent.source.source_name)
            up = DatasetRef.from_source(src, ent.source.schema_, ent.source.table)
            down = DatasetRef.from_target(ent)
            graph.datasets.update({up, down})
            graph.dataset_edges.append(DatasetEdge(up, down, ent.metadata.name))
            for col in ent.mapping:
                for src_col in col.source_columns():
                    graph.column_edges.append(
                        ColumnEdge(
                            upstream=up,
                            upstream_column=src_col,
                            downstream=down,
                            downstream_column=col.target,
                            job=ent.metadata.name,
                        )
                    )
        return graph
