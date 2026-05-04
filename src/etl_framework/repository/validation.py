"""Cross-entity validation passes.

Pydantic validators enforce *intra-document* invariants. This module enforces
*inter-document* invariants:

* every ``EntitySource.ref`` resolves to a known SourceSpec;
* every ``schedule.depends_on`` resolves to a known entity;
* the dependency graph contains no cycles;
* every entity referenced by ``IncrementalLoad`` has a non-empty
  ``watermark_column`` in the source ExtractSpec or relies on a target-side
  watermark column that exists in the mapping.
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
    """Run all cross-entity checks and return the collected issues."""
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
                    f"source '{ent.source.source_name}' referenced by source.ref="
                    f"'{ent.source.ref}' is not defined under sources/",
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
                        "error", name, f"depends_on references unknown entity '{dep}'"
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
                "dependency cycle detected: " + " -> ".join(f"{u}->{v}" for u, v in cycle),
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
                        f"incremental watermark_column '{ent.load.watermark_column}' "
                        "is not present in mapping",
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
                    f"target table '{fqn}' is also written by entity '{seen[fqn]}'",
                )
            )
        else:
            seen[fqn] = name
    return out


def topological_order(repo: MetadataRepository) -> list[EntitySpec]:
    """Return entities in dependency order, suitable for batch generation/loads."""
    graph: nx.DiGraph = nx.DiGraph()
    for name in repo.entities:
        graph.add_node(name)
    for name, ent in repo.entities.items():
        for dep in ent.schedule.depends_on:
            if dep in repo.entities:
                graph.add_edge(dep, name)
    return [repo.entity(n) for n in nx.topological_sort(graph)]
