"""Экспорт графа происхождения данных в формате OpenLineage (JSON).

Выходной формат соответствует спецификации OpenLineage 1.x
(https://openlineage.io/spec/) — формируется список событий COMPLETE,
по одному на каждую ETL-задачу, с фасетом column-level lineage.

Экспортер не зависит от python-клиента OpenLineage; он отдаёт обычные
словари, которые можно отправить в любой OL-бэкенд (Marquez,
самописный HTTP) или сохранить на диск для офлайн-анализа.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .builder import DatasetEdge, DatasetRef, LineageGraph


class OpenLineageExporter:
    PRODUCER = "https://github.com/etl-framework/etl-framework"

    def to_events(self, graph: LineageGraph, run_started: datetime | None = None) -> list[dict]:
        ts = (run_started or datetime.now(timezone.utc)).isoformat(timespec="seconds")
        edges_by_job: dict[str, list[DatasetEdge]] = {}
        for de in graph.dataset_edges:
            edges_by_job.setdefault(de.job, []).append(de)

        events: list[dict] = []
        for job, edges in edges_by_job.items():
            inputs = [self._dataset(de.upstream) for de in edges]
            outputs = []
            for de in edges:
                col_edges = [
                    ce for ce in graph.column_edges
                    if ce.job == job and ce.downstream == de.downstream
                ]
                outputs.append(self._dataset_with_facets(de.downstream, col_edges))
            events.append(
                {
                    "eventType": "COMPLETE",
                    "eventTime": ts,
                    "producer": self.PRODUCER,
                    "schemaURL": "https://openlineage.io/spec/1-0-5/OpenLineage.json",
                    "run": {"runId": str(uuid.uuid4())},
                    "job": {"namespace": "etl-framework", "name": job},
                    "inputs": inputs,
                    "outputs": outputs,
                }
            )
        return events

    def write(self, graph: LineageGraph, path: Path) -> Path:
        events = self.to_events(graph)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(events, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    # ------------------------------------------------------------- хелперы

    @staticmethod
    def _dataset(ref: DatasetRef) -> dict:
        return {"namespace": ref.namespace, "name": ref.name}

    def _dataset_with_facets(self, ref: DatasetRef, column_edges: list) -> dict:
        if not column_edges:
            return self._dataset(ref)
        fields: dict[str, dict] = {}
        for ce in column_edges:
            fields.setdefault(
                ce.downstream_column,
                {"inputFields": []},
            )["inputFields"].append(
                {
                    "namespace": ce.upstream.namespace,
                    "name": ce.upstream.name,
                    "field": ce.upstream_column,
                }
            )
        return {
            **self._dataset(ref),
            "facets": {
                "columnLineage": {
                    "_producer": self.PRODUCER,
                    "_schemaURL": "https://openlineage.io/spec/facets/1-0-1/ColumnLineageDatasetFacet.json",
                    "fields": fields,
                }
            },
        }
