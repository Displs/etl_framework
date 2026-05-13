"""Файловый YAML-репозиторий активных метаданных.

Соглашение о структуре каталогов:

::

    <root>/
        sources/*.yaml      # документы SourceSpec
        entities/*.yaml     # документы EntitySpec

Репозиторий намеренно read-only во время работы фреймворка: авторинг
спецификаций ведётся через git/PR, а не через фреймворк. Это сохраняет
принцип «единого источника истины» из главы 2.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError as PydanticValidationError

from ..models import EntitySpec, SourceSpec


class RepositoryError(Exception):
    """Поднимается, если репозиторий повреждён (нет каталогов, битый YAML и т. п.)."""


class MetadataRepository:
    """Индекс всех загруженных спецификаций в оперативной памяти."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self._sources: dict[str, SourceSpec] = {}
        self._entities: dict[str, EntitySpec] = {}
        self._entity_paths: dict[str, Path] = {}

    # ------------------------------------------------------------------ загрузка

    def load(self) -> None:
        if not self.root.is_dir():
            raise RepositoryError(f"корень репозитория не существует: {self.root}")

        for path in self._iter_yaml(self.root / "sources"):
            spec = self._parse(path, SourceSpec)
            if spec.name in self._sources:
                raise RepositoryError(
                    f"дубликат имени источника '{spec.name}' (второе появление: {path})"
                )
            self._sources[spec.name] = spec

        for path in self._iter_yaml(self.root / "entities"):
            spec = self._parse(path, EntitySpec)
            name = spec.metadata.name
            if name in self._entities:
                raise RepositoryError(
                    f"дубликат имени сущности '{name}' (второе появление: {path})"
                )
            self._entities[name] = spec
            self._entity_paths[name] = path

    @staticmethod
    def _iter_yaml(dir_: Path) -> Iterator[Path]:
        if not dir_.is_dir():
            return
        for path in sorted(dir_.iterdir()):
            if path.is_file() and path.suffix in {".yaml", ".yml"}:
                yield path

    @staticmethod
    def _parse(path: Path, model: type) -> Any:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise RepositoryError(f"{path}: некорректный YAML: {exc}") from exc
        if not isinstance(data, dict):
            raise RepositoryError(f"{path}: ожидался mapping в корне документа")
        try:
            return model.model_validate(data)
        except PydanticValidationError as exc:
            raise RepositoryError(f"{path}: {exc}") from exc

    # --------------------------------------------------------------- доступ

    @property
    def sources(self) -> dict[str, SourceSpec]:
        return dict(self._sources)

    @property
    def entities(self) -> dict[str, EntitySpec]:
        return dict(self._entities)

    def entity(self, name: str) -> EntitySpec:
        try:
            return self._entities[name]
        except KeyError as exc:
            raise KeyError(f"сущность '{name}' не найдена в репозитории") from exc

    def source(self, name: str) -> SourceSpec:
        try:
            return self._sources[name]
        except KeyError as exc:
            raise KeyError(f"источник '{name}' не найден в репозитории") from exc

    def entity_path(self, name: str) -> Path:
        return self._entity_paths[name]
