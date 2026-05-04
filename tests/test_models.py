"""Tests for the Pydantic metadata models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from etl_framework.models import (
    AuditSpec,
    ColumnMapping,
    EntityMetadata,
    EntitySource,
    EntitySpec,
    Layer,
    SCD2Load,
    TargetTable,
)


def _minimal_entity(**overrides):
    base = dict(
        metadata=EntityMetadata(name="stg_x", layer=Layer.STG),
        source=EntitySource(ref="postgres_oltp.public.x"),
        target=TargetTable(catalog="warehouse", schema="stg", table="x"),
        load={"strategy": "full"},
        mapping=[ColumnMapping(target="id", type="BIGINT", source="id", pk=True)],
    )
    base.update(overrides)
    return EntitySpec.model_validate(base)


def test_entity_minimal_ok():
    ent = _minimal_entity()
    assert ent.metadata.name == "stg_x"
    assert ent.target.fqn == "warehouse.stg.x"
    assert ent.primary_keys == ["id"]


def test_duplicate_target_columns_rejected():
    with pytest.raises(ValidationError) as exc:
        _minimal_entity(
            mapping=[
                ColumnMapping(target="x", type="INT", source="a"),
                ColumnMapping(target="x", type="INT", source="b"),
            ]
        )
    assert "duplicate target column" in str(exc.value)


def test_scd2_requires_business_keys_and_tracked():
    with pytest.raises(ValidationError):
        _minimal_entity(
            load={"strategy": "scd2", "business_keys": [], "tracked_columns": ["x"]}
        )


def test_scd2_business_keys_must_exist():
    with pytest.raises(ValidationError) as exc:
        _minimal_entity(
            load=SCD2Load(
                business_keys=["nonexistent"], tracked_columns=["id"]
            ).model_dump(),
            mapping=[
                ColumnMapping(target="id", type="BIGINT", source="id"),
            ],
        )
    assert "business_keys" in str(exc.value)


def test_scd2_technical_columns_must_not_collide():
    with pytest.raises(ValidationError) as exc:
        _minimal_entity(
            load={
                "strategy": "scd2",
                "business_keys": ["id"],
                "tracked_columns": ["name"],
                "effective_from": "valid_from",
            },
            mapping=[
                ColumnMapping(target="id", type="BIGINT", source="id"),
                ColumnMapping(target="name", type="STRING", source="name"),
                ColumnMapping(target="valid_from", type="TIMESTAMP", source="vf"),
            ],
        )
    assert "must not be present in mapping" in str(exc.value)


def test_column_mapping_expression_is_exclusive():
    with pytest.raises(ValidationError):
        ColumnMapping(target="x", type="INT", source="a", expression="a + 1")


def test_column_mapping_render_with_transform_and_default():
    cm = ColumnMapping(
        target="email",
        type="VARCHAR(120)",
        source="email",
        transform="lower(trim($))",
        null_default="''",
    )
    assert cm.render_expression() == "cast(coalesce(lower(trim(email)), '') as VARCHAR(120))"


def test_column_mapping_source_columns():
    cm = ColumnMapping(target="x", type="INT", source="src_x")
    assert cm.source_columns() == ["src_x"]
    expr = ColumnMapping(target="x", type="INT", expression="a + b")
    assert expr.source_columns() == []


def test_audit_defaults():
    spec = AuditSpec()
    assert spec.load_ts_column == "load_ts"
    assert spec.record_hash_column == "record_hash"
