"""Кросс-сущностные проверки репозитория.

Валидаторы Pydantic обеспечивают *внутридокументные* инварианты. Этот
модуль реализует *межсущностные* проверки:

* каждая ``EntitySource.ref`` указывает на известный SourceSpec;
* каждая запись в ``schedule.depends_on`` ссылается на известную сущность;
* граф зависимостей не содержит циклов;
* колонка-маркер инкрементальной загрузки присутствует в маппинге.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from ..models import EntitySpec, IncrementalLoad
from .yaml_repo import MetadataRepository


@dataclass(frozen=True)
class ValidationIssue:
    severity: str  # "error" | "warning"
    entity: str | None
    message: str

    def __str__(self) -> str:
        location = self.entity if self.entity else "<global>"
        return f"[{self.severity.upper()}] {location}: {self.message}"


class ValidationError(Exception):
    def __init__(self, issues: list[ValidationIssue]):
        self.issues = issues
        msg = "\n".join(str(i) for i in issues)
        super().__init__(msg)


def validate_repository(repo: MetadataRepository) -> list[ValidationIssue]:
    """Запустить все межсущностные проверки и вернуть список замечаний."""
    issues: list[ValidationIssue] = []
    issues.extend(_check_source_refs(repo))
    issues.extend(_check_dependencies(repo))
    issues.extend(_check_watermarks(repo))
    issues.extend(_check_target_uniqueness(repo))
    return issues


def _check_source_refs(repo: MetadataRepository) -> list[ValidationIssue]:
    out = []
    for name, ent in repo.entities.items():
        if ent.source.source_name not in repo.sources:
            out.append(
                ValidationIssue(
                    "error",
                    name,
                    f"источник '{ent.source.source_name}', указанный в source.ref="
                    f"'{ent.source.ref}', не определён в каталоге sources/",
                )
            )
    return out


def _check_dependencies(repo: MetadataRepository) -> list[ValidationIssue]:
    out: list[ValidationIssue] = []
    graph: nx.DiGraph = nx.DiGraph()
    for name in repo.entities:
        graph.add_node(name)
    for name, ent in repo.entities.items():
        for dep in ent.schedule.depends_on:
            if dep not in repo.entities:
                out.append(
                    ValidationIssue(
                        "error",
                        name,
                        f"depends_on ссылается на неизвестную сущность '{dep}'",
                    )
                )
                continue
            graph.add_edge(dep, name)
    try:
        cycle = nx.find_cycle(graph)
        out.append(
            ValidationIssue(
                "error",
                None,
                "обнаружен цикл в зависимостях: " + " -> ".join(f"{u}->{v}" for u, v in cycle),
            )
        )
    except nx.NetworkXNoCycle:
        pass
    return out


def _check_watermarks(repo: MetadataRepository) -> list[ValidationIssue]:
    out: list[ValidationIssue] = []
    for name, ent in repo.entities.items():
        if isinstance(ent.load, IncrementalLoad):
            target_cols = {col.target for col in ent.mapping}
            if ent.load.watermark_column not in target_cols:
                out.append(
                    ValidationIssue(
                        "error",
                        name,
                        f"колонка-маркер инкрементальной загрузки "
                        f"'{ent.load.watermark_column}' отсутствует в mapping",
                    )
                )
    return out


def _check_target_uniqueness(repo: MetadataRepository) -> list[ValidationIssue]:
    out = []
    seen: dict[str, str] = {}
    for name, ent in repo.entities.items():
        fqn = ent.target.fqn
        if fqn in seen:
            out.append(
                ValidationIssue(
                    "error",
                    name,
                    f"в целевую таблицу '{fqn}' также пишет сущность '{seen[fqn]}'",
                )
            )
        else:
            seen[fqn] = name
    return out


def topological_order(repo: MetadataRepository) -> list[EntitySpec]:
    """Вернуть сущности в порядке зависимостей — пригодно для пакетной генерации/загрузки."""
    graph: nx.DiGraph = nx.DiGraph()
    for name in repo.entities:
        graph.add_node(name)
    for name, ent in repo.entities.items():
        for dep in ent.schedule.depends_on:
            if dep in repo.entities:
                graph.add_edge(dep, name)
    return [repo.entity(n) for n in nx.topological_sort(graph)]
