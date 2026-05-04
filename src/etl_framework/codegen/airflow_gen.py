"""Render Airflow DAGs from a metadata repository.

The generator emits **one DAG per layer** (stg/ods/dds/dm). Each DAG schedule
is the most frequent schedule among its entities, falling back to ``@daily``.
Cross-layer dependencies become Airflow ``ExternalTaskSensor`` references in a
later iteration; for v0.1 we keep them implicit by ordering layers in the
dependency graph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .. import __version__
from ..models import EntitySpec, Layer, LoadStrategy
from ..repository import MetadataRepository


@dataclass
class _TaskDescriptor:
    name: str
    is_incremental: bool
    depends_on: list[str] = field(default_factory=list)


class AirflowDagGenerator:
    def __init__(self, template_dir: Path | None = None, application_root: str = "/opt/etl/pyspark"):
        if template_dir is None:
            with resources.as_file(
                resources.files("etl_framework").joinpath("codegen/templates/airflow")
            ) as p:
                template_dir = Path(p)
        self._env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._application_root = application_root

    # ------------------------------------------------------------------ API

    def render_layer(self, repo: MetadataRepository, layer: Layer) -> str:
        layer_entities = [e for e in repo.entities.values() if e.metadata.layer == layer]
        if not layer_entities:
            raise ValueError(f"no entities for layer {layer.value}")

        tasks = [
            _TaskDescriptor(
                name=ent.metadata.name,
                is_incremental=(ent.load.strategy == LoadStrategy.INCREMENTAL),
                depends_on=[
                    d for d in ent.schedule.depends_on
                    if d in {x.metadata.name for x in layer_entities}
                ],
            )
            for ent in _topo_within_layer(layer_entities)
        ]

        # Pick the most-frequent cron among layer entities; fallback to @daily.
        crons = [e.schedule.cron for e in layer_entities]
        cron = max(set(crons), key=crons.count) if crons else "@daily"
        catchups = [e.schedule.catchup for e in layer_entities]
        retries = max((e.schedule.retries for e in layer_entities), default=2)
        retry_delay = max(
            (e.schedule.retry_delay_minutes for e in layer_entities), default=5
        )
        start_dates = [e.schedule.start_date for e in layer_entities]

        template = self._env.get_template("dag.py.j2")
        return template.render(
            framework_version=__version__,
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            dag_id=f"etl_{layer.value}",
            tasks=tasks,
            cron=cron,
            catchup=any(catchups),
            default_retries=retries,
            default_retry_delay=retry_delay,
            start_date=min(start_dates),
            application_root=self._application_root,
        )

    def render_all(self, repo: MetadataRepository) -> dict[Layer, str]:
        out: dict[Layer, str] = {}
        present = {e.metadata.layer for e in repo.entities.values()}
        for layer in present:
            out[layer] = self.render_layer(repo, layer)
        return out


def _topo_within_layer(entities: list[EntitySpec]) -> list[EntitySpec]:
    """Order entities within a layer by intra-layer dependencies."""
    import networkx as nx

    g: nx.DiGraph = nx.DiGraph()
    by_name = {e.metadata.name: e for e in entities}
    for e in entities:
        g.add_node(e.metadata.name)
    for e in entities:
        for dep in e.schedule.depends_on:
            if dep in by_name:
                g.add_edge(dep, e.metadata.name)
    return [by_name[n] for n in nx.topological_sort(g)]
