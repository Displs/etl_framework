"""PostgreSQL discovery via SQLAlchemy reflection.

The discoverer connects to a source via the connection details from a
``SourceSpec`` and emits a draft ``EntitySpec`` skeleton (as a Python dict
suitable for ``yaml.dump``). It does **not** write to disk — that is the CLI's
job.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import MetaData, Table, create_engine, inspect
from sqlalchemy.engine import Engine

from ..models import Layer, SourceSpec
from ..security.secrets import resolve_secret

# Map of PostgreSQL types to canonical Spark/SQL types used in the EntitySpec.
# Conservative — anything unknown becomes STRING.
_PG_TO_CANONICAL: dict[str, str] = {
    "smallint": "SMALLINT",
    "integer": "INT",
    "bigint": "BIGINT",
    "boolean": "BOOLEAN",
    "real": "FLOAT",
    "double precision": "DOUBLE",
    "numeric": "DECIMAL(38,9)",
    "text": "STRING",
    "uuid": "STRING",
    "date": "DATE",
    "timestamp without time zone": "TIMESTAMP",
    "timestamp with time zone": "TIMESTAMP",
    "json": "STRING",
    "jsonb": "STRING",
    "bytea": "BINARY",
}


def _canonical_type(pg_type: str, length: int | None) -> str:
    base = pg_type.lower()
    if base.startswith("character varying") or base == "character":
        return f"VARCHAR({length})" if length else "STRING"
    if base in _PG_TO_CANONICAL:
        return _PG_TO_CANONICAL[base]
    return "STRING"


@dataclass
class DiscoveredColumn:
    name: str
    type: str
    nullable: bool
    primary_key: bool


@dataclass
class DiscoveredTable:
    schema: str
    table: str
    columns: list[DiscoveredColumn]

    @property
    def primary_keys(self) -> list[str]:
        return [c.name for c in self.columns if c.primary_key]


class PostgresDiscoverer:
    """Wraps a SQLAlchemy engine for repeated reflection calls."""

    def __init__(self, source: SourceSpec):
        if source.connection.kind.value != "postgres":
            raise ValueError(
                f"PostgresDiscoverer can only discover postgres sources, "
                f"got '{source.connection.kind.value}'"
            )
        self.source = source
        self._engine: Engine | None = None

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            conn = self.source.connection
            password = resolve_secret(conn.password)
            user = resolve_secret(conn.user)
            url = (
                f"postgresql+psycopg2://{user}:{password}"
                f"@{conn.host}:{conn.port}/{conn.database}"
            )
            self._engine = create_engine(url, future=True)
        return self._engine

    def discover(self, schema: str, table: str) -> DiscoveredTable:
        inspector = inspect(self.engine)
        cols_info = inspector.get_columns(table, schema=schema)
        if not cols_info:
            raise ValueError(f"table {schema}.{table} not found or empty")
        pk_info = inspector.get_pk_constraint(table, schema=schema) or {}
        pk_cols = set(pk_info.get("constrained_columns") or [])

        # SQLAlchemy gives a "type" object, but its string form is dialect-specific;
        # we re-read information_schema for portable type names.
        meta = MetaData()
        sqla_table = Table(table, meta, autoload_with=self.engine, schema=schema)
        cols: list[DiscoveredColumn] = []
        for c in sqla_table.columns:
            length = getattr(c.type, "length", None)
            type_str = c.type.compile(dialect=self.engine.dialect)
            cols.append(
                DiscoveredColumn(
                    name=c.name,
                    type=_canonical_type(type_str, length),
                    nullable=c.nullable if c.nullable is not None else True,
                    primary_key=c.name in pk_cols,
                )
            )
        return DiscoveredTable(schema=schema, table=table, columns=cols)


def discover_table(
    source: SourceSpec,
    schema: str,
    table: str,
    *,
    target_layer: Layer = Layer.STG,
    target_schema: str | None = None,
    target_table: str | None = None,
) -> dict[str, Any]:
    """Return a dict ready to be dumped as the YAML body of an EntitySpec stub.

    The stub uses ``full`` load strategy and direct mappings; the engineer is
    expected to refine it (especially for SCD tables).
    """
    discovered = PostgresDiscoverer(source).discover(schema, table)
    target_schema = target_schema or target_layer.value
    target_table = target_table or f"{target_layer.value}_{table}"

    mapping = []
    for col in discovered.columns:
        item: dict[str, Any] = {
            "target": col.name,
            "type": col.type,
            "source": col.name,
        }
        if col.primary_key:
            item["pk"] = True
        mapping.append(item)

    return {
        "apiVersion": "etlf/v1",
        "kind": "Entity",
        "metadata": {
            "name": f"{target_layer.value}_{table}",
            "layer": target_layer.value,
            "description": f"Auto-discovered from {source.name}.{schema}.{table}",
        },
        "source": {"ref": f"{source.name}.{schema}.{table}"},
        "target": {
            "catalog": "warehouse",
            "schema": target_schema,
            "table": target_table,
            "format": "iceberg",
        },
        "load": {"strategy": "full"},
        "mapping": mapping,
        "schedule": {"cron": "@daily"},
    }
