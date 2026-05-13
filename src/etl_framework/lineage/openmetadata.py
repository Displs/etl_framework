"""Публикация ``LineageGraph`` в OpenMetadata через официальный SDK.

SDK поставляется как ``openmetadata-ingestion`` и объявлен extras-зависимостью
(``etl-framework[openmetadata]``). Импорт ленивый: проекты, которые
публикуют lineage другими средствами (OpenLineage JSON, собственный
ingestion), не платят за импорт SDK.

Публикатор **не регистрирует** таблицы источников и целевые таблицы — он
предполагает, что они уже занесены в OpenMetadata стандартными
коннекторами ingestion. Поиск таблиц идёт по FQN, и при отсутствии
зависимости публикатор громко падает, чтобы избежать «призраков»
в каталоге.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .builder import ColumnEdge, DatasetRef, LineageGraph

log = logging.getLogger(__name__)


@dataclass
class OpenMetadataConfig:
    host_port: str  # например, "http://openmetadata-server:8585/api"
    jwt_token: str
    # Iceberg-таблицы фреймворка регистрируются в OpenMetadata под
    # database-сервисом с указанным именем. FQN источников ищутся по
    # ключу-схеме коннекции (postgres/clickhouse/...), при необходимости
    # переопределяемому через ``source_service_overrides``.
    iceberg_service: str = "iceberg_warehouse"
    source_service_overrides: dict[str, str] | None = None


class OpenMetadataPublisher:
    """Публикует рёбра lineage в инстанс OpenMetadata."""

    def __init__(self, config: OpenMetadataConfig):
        self.config = config
        self._client: Any | None = None

    # ---------------------------------------------------------------- bootstrap

    def _connect(self) -> Any:
        if self._client is not None:
            return self._client
        try:  # pragma: no cover — выполняется только если SDK установлен
            from metadata.generated.schema.entity.services.connections.metadata.openMetadataConnection import (
                AuthProvider,
                OpenMetadataConnection,
            )
            from metadata.generated.schema.security.client.openMetadataJWTClientConfig import (
                OpenMetadataJWTClientConfig,
            )
            from metadata.ingestion.ometa.ometa_api import OpenMetadata
        except ImportError as exc:
            raise RuntimeError(
                "SDK OpenMetadata не установлен; переустановите фреймворк с extras: "
                "'pip install etl-framework[openmetadata]'"
            ) from exc

        cfg = OpenMetadataConnection(
            hostPort=self.config.host_port,
            authProvider=AuthProvider.openmetadata,
            securityConfig=OpenMetadataJWTClientConfig(jwtToken=self.config.jwt_token),
        )
        self._client = OpenMetadata(cfg)
        return self._client

    # -------------------------------------------------------------------- API

    def publish(self, graph: LineageGraph) -> int:
        """Опубликовать все рёбра датасетов и колонок. Возвращает число вызовов API."""
        client = self._connect()
        from metadata.generated.schema.api.lineage.addLineage import AddLineageRequest
        from metadata.generated.schema.type.entityLineage import (
            ColumnLineage,
            EntitiesEdge,
            LineageDetails,
        )
        from metadata.generated.schema.type.entityReference import EntityReference

        # Группируем колоночные рёбра по тройке (upstream, downstream, job),
        # чтобы один AddLineageRequest содержал все колонки одного
        # датасетного ребра.
        per_edge: dict[tuple[DatasetRef, DatasetRef, str], list[ColumnEdge]] = {}
        for ce in graph.column_edges:
            per_edge.setdefault((ce.upstream, ce.downstream, ce.job), []).append(ce)

        calls = 0
        for de in graph.dataset_edges:
            up_ref = self._resolve(client, de.upstream, EntityReference)
            down_ref = self._resolve(client, de.downstream, EntityReference)
            col_edges = per_edge.get((de.upstream, de.downstream, de.job), [])
            column_lineage = [
                ColumnLineage(
                    fromColumns=[self._column_fqn(de.upstream, ce.upstream_column)],
                    toColumn=self._column_fqn(de.downstream, ce.downstream_column),
                )
                for ce in col_edges
            ]
            details = LineageDetails(
                pipeline=None,
                description=f"сгенерировано etl-framework, задача {de.job}",
                columnsLineage=column_lineage or None,
            )
            req = AddLineageRequest(
                edge=EntitiesEdge(
                    fromEntity=up_ref, toEntity=down_ref, lineageDetails=details
                )
            )
            client.add_lineage(data=req)
            calls += 1
        log.info("опубликовано рёбер lineage: %d на %s", calls, self.config.host_port)
        return calls

    # ----------------------------------------------------------- внутренние

    def _resolve(self, client: Any, ref: DatasetRef, EntityReference: Any) -> Any:
        from metadata.generated.schema.entity.data.table import Table

        fqn = self._table_fqn(ref)
        table = client.get_by_name(entity=Table, fqn=fqn)
        if table is None:
            raise RuntimeError(
                f"OpenMetadata: таблица '{fqn}' не найдена; запустите ingestion "
                "до публикации lineage"
            )
        return EntityReference(id=table.id, type="table")

    def _table_fqn(self, ref: DatasetRef) -> str:
        # Iceberg-цели лежат под сервисом с настраиваемым именем.
        if ref.namespace.startswith("iceberg://"):
            db = ref.namespace.removeprefix("iceberg://")
            schema, table = ref.name.split(".", 1)
            return f"{self.config.iceberg_service}.{db}.{schema}.{table}"

        # Источники: имя сервиса берётся из overrides или из схемы URI.
        scheme = ref.namespace.split("://", 1)[0]
        overrides = self.config.source_service_overrides or {}
        service = overrides.get(scheme, scheme)
        # namespace вида "postgres://host:5432/db" — нужно имя БД в конце.
        try:
            db = ref.namespace.rsplit("/", 1)[1]
        except IndexError:
            db = "default"
        schema, table = ref.name.split(".", 1)
        return f"{service}.{db}.{schema}.{table}"

    def _column_fqn(self, ref: DatasetRef, column: str) -> str:
        return f"{self._table_fqn(ref)}.{column}"
