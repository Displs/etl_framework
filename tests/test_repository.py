"""Repository loading and cross-entity validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from etl_framework.repository import (
    MetadataRepository,
    validate_repository,
)
from etl_framework.repository.validation import topological_order
from etl_framework.repository.yaml_repo import RepositoryError


def test_loads_all_examples(retail_repo: MetadataRepository):
    assert "postgres_oltp" in retail_repo.sources
    assert {"stg_clients", "ods_orders", "dds_clients", "dds_products", "dm_orders_daily"} <= set(
        retail_repo.entities
    )


def test_validation_clean(retail_repo: MetadataRepository):
    issues = validate_repository(retail_repo)
    errors = [i for i in issues if i.severity == "error"]
    assert errors == []


def test_topological_order_respects_deps(retail_repo: MetadataRepository):
    order = [e.metadata.name for e in topological_order(retail_repo)]
    # dds_clients depends on stg_clients
    assert order.index("stg_clients") < order.index("dds_clients")
    # dm_orders_daily depends on ods_orders
    assert order.index("ods_orders") < order.index("dm_orders_daily")


def test_unknown_source_ref_is_error(tmp_path: Path):
    (tmp_path / "sources").mkdir()
    (tmp_path / "entities").mkdir()
    (tmp_path / "sources" / "good.yaml").write_text(
        "name: good\n"
        "connection:\n"
        "  kind: postgres\n  host: h\n  port: 5432\n  database: d\n"
        "  user: u\n  password: p\n",
        encoding="utf-8",
    )
    (tmp_path / "entities" / "bad.yaml").write_text(
        "apiVersion: etlf/v1\nkind: Entity\n"
        "metadata: { name: bad, layer: stg }\n"
        "source: { ref: missing.public.t }\n"
        "target: { catalog: w, schema: stg, table: t }\n"
        "load: { strategy: full }\n"
        "mapping: [{ target: x, type: INT, source: x }]\n",
        encoding="utf-8",
    )
    repo = MetadataRepository(tmp_path)
    repo.load()
    issues = validate_repository(repo)
    assert any("missing" in i.message for i in issues if i.severity == "error")


def test_dependency_cycle_detected(tmp_path: Path):
    (tmp_path / "sources").mkdir()
    (tmp_path / "entities").mkdir()
    (tmp_path / "sources" / "s.yaml").write_text(
        "name: s\nconnection: {kind: postgres, host: h, port: 5432, database: d, user: u, password: p}\n",
        encoding="utf-8",
    )
    for n, dep in [("a", "b"), ("b", "a")]:
        (tmp_path / "entities" / f"{n}.yaml").write_text(
            "apiVersion: etlf/v1\nkind: Entity\n"
            f"metadata: {{ name: {n}, layer: stg }}\n"
            "source: { ref: s.public.t }\n"
            f"target: {{ catalog: w, schema: stg, table: {n} }}\n"
            "load: { strategy: full }\n"
            "mapping: [{ target: x, type: INT, source: x }]\n"
            f"schedule: {{ depends_on: [{dep}] }}\n",
            encoding="utf-8",
        )
    repo = MetadataRepository(tmp_path)
    repo.load()
    issues = validate_repository(repo)
    assert any("cycle" in i.message for i in issues if i.severity == "error")


def test_target_collision_detected(tmp_path: Path):
    (tmp_path / "sources").mkdir()
    (tmp_path / "entities").mkdir()
    (tmp_path / "sources" / "s.yaml").write_text(
        "name: s\nconnection: {kind: postgres, host: h, port: 5432, database: d, user: u, password: p}\n",
        encoding="utf-8",
    )
    for n in ("a", "b"):
        (tmp_path / "entities" / f"{n}.yaml").write_text(
            "apiVersion: etlf/v1\nkind: Entity\n"
            f"metadata: {{ name: {n}, layer: stg }}\n"
            "source: { ref: s.public.t }\n"
            "target: { catalog: w, schema: stg, table: same }\n"
            "load: { strategy: full }\n"
            "mapping: [{ target: x, type: INT, source: x }]\n",
            encoding="utf-8",
        )
    repo = MetadataRepository(tmp_path)
    repo.load()
    issues = validate_repository(repo)
    assert any("also written" in i.message for i in issues if i.severity == "error")


def test_invalid_yaml_raises(tmp_path: Path):
    (tmp_path / "sources").mkdir()
    (tmp_path / "entities").mkdir()
    (tmp_path / "sources" / "broken.yaml").write_text(":\n  - bad\nbad", encoding="utf-8")
    repo = MetadataRepository(tmp_path)
    with pytest.raises(RepositoryError):
        repo.load()
