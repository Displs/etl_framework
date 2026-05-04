"""Command-line interface for the ETL framework.

Commands:
    validate    — load and validate the metadata repository
    generate    — render PySpark + Airflow DAGs into an output directory
    discover    — produce a draft EntitySpec from a Postgres table
    lineage     — export OpenLineage JSON / publish to OpenMetadata
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

from ..codegen import AirflowDagGenerator, CodegenEngine, SqlSinkGenerator
from ..discovery import discover_table
from ..lineage import LineageBuilder, OpenLineageExporter, OpenMetadataPublisher
from ..lineage.openmetadata import OpenMetadataConfig
from ..models import Layer
from ..repository import MetadataRepository, ValidationError, validate_repository
from ..security import AuditLogger, audit_event

app = typer.Typer(add_completion=False, no_args_is_help=True, pretty_exceptions_enable=False)
console = Console()


def _load_repo(root: Path) -> MetadataRepository:
    repo = MetadataRepository(root)
    repo.load()
    return repo


# ----------------------------------------------------------------- validate


@app.command()
def validate(
    root: Path = typer.Argument(..., help="Repository root containing sources/ and entities/"),
) -> None:
    """Validate all specs and cross-entity invariants."""
    try:
        repo = _load_repo(root)
    except Exception as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(2) from exc

    issues = validate_repository(repo)
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    table = Table(title=f"Repository: {root}")
    table.add_column("entities", justify="right")
    table.add_column("sources", justify="right")
    table.add_column("errors", justify="right", style="red")
    table.add_column("warnings", justify="right", style="yellow")
    table.add_row(
        str(len(repo.entities)),
        str(len(repo.sources)),
        str(len(errors)),
        str(len(warnings)),
    )
    console.print(table)

    for issue in issues:
        style = "red" if issue.severity == "error" else "yellow"
        console.print(f"[{style}]{issue}[/{style}]")

    if errors:
        raise typer.Exit(1)


# ----------------------------------------------------------------- generate


@app.command()
def generate(
    root: Path = typer.Argument(..., help="Repository root"),
    output: Path = typer.Option(Path("build"), "-o", "--output", help="Output directory"),
    sql_sinks: bool = typer.Option(False, help="Emit SQL DDL for external sinks"),
) -> None:
    """Render PySpark scripts and Airflow DAGs into ``output``."""
    repo = _load_repo(root)
    issues = validate_repository(repo)
    if any(i.severity == "error" for i in issues):
        for i in issues:
            console.print(f"[red]{i}[/red]")
        raise ValidationError([i for i in issues if i.severity == "error"])

    audit = AuditLogger(output)
    audit.log(audit_event("generate.start", details={"root": str(root)}))

    engine = CodegenEngine()
    artifacts = engine.generate_repository(repo, output)
    for art in artifacts:
        path = art.write(output)
        console.print(f"[green]wrote[/green] {path} (sha256={art.checksum[:12]})")

    dag_gen = AirflowDagGenerator()
    for layer, content in dag_gen.render_all(repo).items():
        path = output / "airflow" / f"etl_{layer.value}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        console.print(f"[green]wrote[/green] {path}")

    if sql_sinks:
        sql_gen = SqlSinkGenerator()
        for ent in repo.entities.values():
            for sink in ent.sinks:
                content = sql_gen.render(ent, sink)
                path = output / "sql" / sink.kind / f"{ent.metadata.name}__{sink.name}.sql"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                console.print(f"[green]wrote[/green] {path}")

    audit.log(audit_event("generate.done", details={"artifacts": str(len(artifacts))}))


# ----------------------------------------------------------------- discover


@app.command()
def discover(
    root: Path = typer.Argument(..., help="Repository root"),
    source: str = typer.Option(..., help="Source name (must exist under sources/)"),
    schema: str = typer.Option(..., help="Source schema"),
    table: str = typer.Option(..., help="Source table"),
    layer: Layer = typer.Option(Layer.STG, help="Target layer"),
    output: Path | None = typer.Option(
        None, "-o", "--output", help="Where to write the YAML; default: stdout"
    ),
) -> None:
    """Produce a draft EntitySpec YAML for a source table."""
    repo = _load_repo(root)
    src = repo.source(source)
    spec = discover_table(src, schema, table, target_layer=layer)
    text = yaml.safe_dump(spec, sort_keys=False, allow_unicode=True)
    if output is None:
        sys.stdout.write(text)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        console.print(f"[green]wrote[/green] {output}")


# ------------------------------------------------------------------- lineage


lineage_app = typer.Typer(help="Lineage utilities", no_args_is_help=True)
app.add_typer(lineage_app, name="lineage")


@lineage_app.command("export")
def lineage_export(
    root: Path = typer.Argument(..., help="Repository root"),
    output: Path = typer.Option(
        Path("build/openlineage.json"), "-o", "--output", help="Output JSON path"
    ),
) -> None:
    """Export the lineage graph as an OpenLineage events JSON file."""
    repo = _load_repo(root)
    graph = LineageBuilder().build(repo)
    written = OpenLineageExporter().write(graph, output)
    console.print(f"[green]wrote[/green] {written}")


@lineage_app.command("publish")
def lineage_publish(
    root: Path = typer.Argument(..., help="Repository root"),
    host_port: str = typer.Option(..., envvar="OPENMETADATA_HOST_PORT"),
    jwt_token: str = typer.Option(..., envvar="OPENMETADATA_JWT", help="JWT bot token"),
    iceberg_service: str = typer.Option(
        "iceberg_warehouse", envvar="OPENMETADATA_ICEBERG_SERVICE"
    ),
) -> None:
    """Publish lineage edges to an OpenMetadata server."""
    repo = _load_repo(root)
    graph = LineageBuilder().build(repo)
    publisher = OpenMetadataPublisher(
        OpenMetadataConfig(
            host_port=host_port, jwt_token=jwt_token, iceberg_service=iceberg_service
        )
    )
    n = publisher.publish(graph)
    console.print(f"[green]published {n} edges[/green]")


def _entrypoint() -> None:
    # Wrapper for setuptools entry point so we can intercept exit codes if needed.
    sys.exit(app(standalone_mode=True))


if __name__ == "__main__":  # pragma: no cover
    _entrypoint()
