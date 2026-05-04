"""Tests for the code-generation engine."""

from __future__ import annotations

import ast

import pytest

from etl_framework.codegen import AirflowDagGenerator, CodegenEngine, SqlSinkGenerator
from etl_framework.repository import MetadataRepository


def test_all_pyspark_artifacts_parse(retail_repo: MetadataRepository):
    eng = CodegenEngine()
    for ent in retail_repo.entities.values():
        src = retail_repo.source(ent.source.source_name)
        code = eng.render_entity(ent, src)
        ast.parse(code)  # raises SyntaxError on bad output


def test_full_load_template_contains_create_or_replace(retail_repo: MetadataRepository):
    ent = retail_repo.entity("stg_clients")
    src = retail_repo.source(ent.source.source_name)
    code = CodegenEngine().render_entity(ent, src)
    assert "createOrReplace()" in code
    assert "warehouse.stg.clients" in code


def test_incremental_template_emits_watermark_clause(retail_repo: MetadataRepository):
    ent = retail_repo.entity("ods_orders")
    src = retail_repo.source(ent.source.source_name)
    code = CodegenEngine().render_entity(ent, src)
    assert "lower_bound" in code
    assert "updated_at" in code
    assert "WATERMARK_COLUMN" in code


def test_scd1_template_uses_merge_into(retail_repo: MetadataRepository):
    ent = retail_repo.entity("dds_products")
    src = retail_repo.source(ent.source.source_name)
    code = CodegenEngine().render_entity(ent, src)
    assert "MERGE INTO" in code
    assert "WHEN MATCHED" in code


def test_scd2_template_two_step_merge(retail_repo: MetadataRepository):
    ent = retail_repo.entity("dds_clients")
    src = retail_repo.source(ent.source.source_name)
    code = CodegenEngine().render_entity(ent, src)
    assert "scd2 step 1" in code
    assert "scd2 step 2" in code
    assert "valid_from" in code and "valid_to" in code and "is_current" in code


def test_codegen_is_deterministic(retail_repo: MetadataRepository):
    eng = CodegenEngine()
    ent = retail_repo.entity("dds_clients")
    src = retail_repo.source(ent.source.source_name)
    a = eng.render_entity(ent, src)
    b = eng.render_entity(ent, src)
    # generated_at differs by seconds; strip the header for the comparison
    a_body = "\n".join(a.splitlines()[5:])
    b_body = "\n".join(b.splitlines()[5:])
    assert a_body == b_body


def test_audit_columns_appear(retail_repo: MetadataRepository):
    ent = retail_repo.entity("stg_clients")
    src = retail_repo.source(ent.source.source_name)
    code = CodegenEngine().render_entity(ent, src)
    assert "load_ts" in code
    assert "source_system" in code
    assert "record_hash" in code  # default audit


def test_unknown_strategy_raises():
    from unittest.mock import MagicMock

    spec = MagicMock()
    spec.load.strategy = "unsupported"
    with pytest.raises(NotImplementedError):
        CodegenEngine().render_entity(spec, MagicMock())


def test_airflow_dag_per_layer(retail_repo: MetadataRepository):
    dags = AirflowDagGenerator().render_all(retail_repo)
    layer_values = {layer.value for layer in dags}
    assert {"stg", "ods", "dds", "dm"} <= layer_values
    for content in dags.values():
        ast.parse(content)
        assert "SparkSubmitOperator" in content
        assert 'tags=["etl-framework", "auto-generated"]' in content


def test_airflow_dag_orders_dependencies(retail_repo: MetadataRepository):
    dags = AirflowDagGenerator().render_all(retail_repo)
    from etl_framework.models import Layer

    dds_dag = dags[Layer.DDS]
    assert 'tasks["stg_clients"] >> tasks["dds_clients"]' not in dds_dag, (
        "cross-layer deps are excluded from in-layer DAG body"
    )
    # within dds, products and clients have no intra-layer deps:
    assert "dds_clients" in dds_dag
    assert "dds_products" in dds_dag


def test_sql_sink_generator_greenplum(retail_repo: MetadataRepository):
    ent = retail_repo.entity("dds_clients")
    sink = ent.sinks[0]
    sql = SqlSinkGenerator().render(ent, sink)
    assert "CREATE TABLE IF NOT EXISTS marts.dim_clients" in sql
    assert "DISTRIBUTED BY" in sql


def test_sql_sink_generator_clickhouse(retail_repo: MetadataRepository):
    ent = retail_repo.entity("dm_orders_daily")
    sink = ent.sinks[0]
    sql = SqlSinkGenerator().render(ent, sink)
    assert "ENGINE = MergeTree" in sql
    assert "ORDER BY" in sql
