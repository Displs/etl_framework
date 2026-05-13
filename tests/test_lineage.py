"""Тесты подсистемы lineage."""

from __future__ import annotations

import json
from pathlib import Path

from etl_framework.lineage import LineageBuilder, OpenLineageExporter
from etl_framework.repository import MetadataRepository


def test_dataset_edges_one_per_entity(retail_repo: MetadataRepository):
    graph = LineageBuilder().build(retail_repo)
    assert len(graph.dataset_edges) == len(retail_repo.entities)


def test_column_edges_match_mappings(retail_repo: MetadataRepository):
    graph = LineageBuilder().build(retail_repo)
    by_job = {e.metadata.name: 0 for e in retail_repo.entities.values()}
    for ce in graph.column_edges:
        by_job[ce.job] += 1
    # каждый прямой/transform-маппинг даёт одно колоночное ребро
    for name, ent in retail_repo.entities.items():
        expected = sum(1 for c in ent.mapping if c.source_columns())
        assert by_job[name] == expected, name


def test_dataset_ref_namespaces(retail_repo: MetadataRepository):
    graph = LineageBuilder().build(retail_repo)
    refs = list(graph.datasets)
    iceberg = [r for r in refs if r.namespace.startswith("iceberg://")]
    pg = [r for r in refs if r.namespace.startswith("postgres://")]
    assert iceberg and pg


def test_openlineage_export_roundtrip(retail_repo: MetadataRepository, tmp_path: Path):
    graph = LineageBuilder().build(retail_repo)
    out = tmp_path / "ol.json"
    OpenLineageExporter().write(graph, out)
    events = json.loads(out.read_text())
    assert len(events) == len(retail_repo.entities)
    for ev in events:
        assert ev["eventType"] == "COMPLETE"
        assert ev["job"]["namespace"] == "etl-framework"
        assert ev["inputs"]
        assert ev["outputs"]


def test_openlineage_includes_column_lineage_facet(retail_repo: MetadataRepository):
    graph = LineageBuilder().build(retail_repo)
    events = OpenLineageExporter().to_events(graph)
    facets_found = False
    for ev in events:
        for out in ev["outputs"]:
            if "facets" in out and "columnLineage" in out["facets"]:
                facets_found = True
                fields = out["facets"]["columnLineage"]["fields"]
                # хотя бы у одной колонки есть хотя бы один input-field
                assert any(f["inputFields"] for f in fields.values())
    assert facets_found
