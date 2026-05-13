"""Рендеринг SQL DDL для внешних приёмников (витрины Greenplum / ClickHouse)."""

from __future__ import annotations

from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .. import __version__
from ..models import EntitySpec, SinkTable


class SqlSinkGenerator:
    def __init__(self, template_dir: Path | None = None):
        if template_dir is None:
            with resources.as_file(
                resources.files("etl_framework").joinpath("codegen/templates/sql")
            ) as p:
                template_dir = Path(p)
        self._env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, spec: EntitySpec, sink: SinkTable) -> str:
        template_name = {
            "greenplum": "greenplum_export.sql.j2",
            "clickhouse": "clickhouse_export.sql.j2",
        }[sink.kind]
        template = self._env.get_template(template_name)
        return template.render(
            spec=spec,
            sink=sink,
            framework_version=__version__,
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
