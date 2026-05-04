"""Code-generation engine.

The engine is intentionally thin: it builds a Jinja2 environment loaded from
``codegen/templates/`` and dispatches each EntitySpec to the template that
matches its load strategy. Adding a new strategy = adding a new template +
one line in ``_TEMPLATE_FOR_STRATEGY``.
"""

from __future__ import annotations

import hashlib
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from .. import __version__
from ..models import EntitySpec, LoadStrategy, SourceSpec
from ..repository import MetadataRepository

_TEMPLATE_FOR_STRATEGY: dict[LoadStrategy, str] = {
    LoadStrategy.FULL: "pyspark/full_load.py.j2",
    LoadStrategy.INCREMENTAL: "pyspark/incremental.py.j2",
    LoadStrategy.SCD1: "pyspark/scd1.py.j2",
    LoadStrategy.SCD2: "pyspark/scd2.py.j2",
}


@dataclass
class GeneratedArtifact:
    relative_path: Path
    content: str
    checksum: str

    def write(self, root: Path) -> Path:
        path = root / self.relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.content, encoding="utf-8")
        return path


class CodegenEngine:
    """Renders artifacts for an entire repository."""

    def __init__(self, template_dir: Path | None = None):
        if template_dir is None:
            with resources.as_file(
                resources.files("etl_framework").joinpath("codegen/templates")
            ) as p:
                template_dir = Path(p)
        self._env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(disabled_extensions=("j2",)),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._env.filters["sql_ident"] = _sql_ident
        self._env.filters["sql_literal"] = _sql_literal
        self._env.filters["py_literal"] = _py_literal
        self._env.filters["dedent"] = textwrap.dedent

    # -------------------------------------------------------------- API

    def render_entity(self, spec: EntitySpec, source: SourceSpec) -> str:
        """Render the PySpark script for one entity."""
        try:
            template_name = _TEMPLATE_FOR_STRATEGY[spec.load.strategy]
        except KeyError as exc:
            raise NotImplementedError(
                f"no template registered for load strategy {spec.load.strategy}"
            ) from exc
        template = self._env.get_template(template_name)
        return template.render(
            spec=spec,
            source=source,
            framework_version=__version__,
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

    def generate_repository(
        self, repo: MetadataRepository, output_dir: Path
    ) -> list[GeneratedArtifact]:
        """Render all entities, returning artifact records."""
        artifacts: list[GeneratedArtifact] = []
        for name, ent in repo.entities.items():
            src = repo.source(ent.source.source_name)
            content = self.render_entity(ent, src)
            rel = Path("pyspark") / f"{name}.py"
            artifacts.append(_artifact(rel, content))
        return artifacts


# -------------------------------------------------------------------- helpers


def _artifact(rel: Path, content: str) -> GeneratedArtifact:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return GeneratedArtifact(relative_path=rel, content=content, checksum=digest)


def _sql_ident(name: str) -> str:
    """Quote a SQL identifier conservatively.

    The Spark SQL parser accepts back-tick quoting and the Iceberg catalog
    namespace style. We use back-ticks to be safe with reserved words.
    """
    return f"`{name}`" if not name.startswith("`") else name


def _sql_literal(value: str | int | float | bool | None) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def _py_literal(value: object) -> str:
    return repr(value)
