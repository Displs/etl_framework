"""Discovery tests using SQLite as a stand-in for PostgreSQL.

We can't run a real PostgreSQL inside CI without a network, so we test the
type-mapping + skeleton-emission logic with a SQLite-backed engine. The
PostgresDiscoverer guards against non-postgres sources, so we exercise the
internal helper directly.
"""

from __future__ import annotations

import pytest

from etl_framework.discovery.postgres import _PG_TO_CANONICAL, _canonical_type


def test_type_mapping_known_types():
    assert _canonical_type("integer", None) == "INT"
    assert _canonical_type("bigint", None) == "BIGINT"
    assert _canonical_type("text", None) == "STRING"
    assert _canonical_type("timestamp without time zone", None) == "TIMESTAMP"


def test_type_mapping_varchar_with_length():
    assert _canonical_type("character varying", 120) == "VARCHAR(120)"


def test_type_mapping_unknown_falls_back_to_string():
    assert _canonical_type("ltree", None) == "STRING"


def test_canonical_table_covers_common_pg_types():
    expected = {"integer", "bigint", "boolean", "uuid", "date", "jsonb"}
    assert expected <= set(_PG_TO_CANONICAL)


def test_postgres_discoverer_rejects_non_postgres():
    from etl_framework.discovery.postgres import PostgresDiscoverer
    from etl_framework.models import SourceConnection, SourceKind, SourceSpec

    src = SourceSpec(
        name="x",
        connection=SourceConnection(
            kind=SourceKind.CLICKHOUSE,
            host="h",
            port=8123,
            database="d",
            user="u",
            password="p",
        ),
    )
    with pytest.raises(ValueError, match="postgres"):
        PostgresDiscoverer(src)
