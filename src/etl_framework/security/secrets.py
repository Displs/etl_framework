"""Разрешение ссылок на секреты.

*Ссылка на секрет* — строка одного из следующих видов:

* ``env:NAME`` — читать из переменной окружения ``NAME``;
* ``file:/path/to/file`` — читать содержимое (одну строку) из файла;
* ``vault:path/to/secret#field`` — заглушка; поднимает ``NotImplementedError``;
* всё остальное — возвращается как есть, трактуется как литеральное значение.

Сгенерированный PySpark-код никогда не содержит литерального значения
секрета. В код подставляется **ссылка**, разрешение выполняется
в runtime той же функцией. Это удерживает секреты вне сгенерированных
артефактов и вне git.
"""

from __future__ import annotations

import os
from pathlib import Path


class SecretResolutionError(Exception):
    """Поднимается, если ссылку на секрет не удалось разрешить."""


def resolve_secret(ref: str) -> str:
    """Разрешить ссылку на секрет в runtime.

    Функция намеренно либеральна: литералы (всё без префикса ``scheme:``)
    проходят насквозь, чтобы примеры можно было писать с понятными
    плейсхолдерами.
    """
    if not isinstance(ref, str):
        raise SecretResolutionError(
            f"ссылка на секрет должна быть строкой, получено {type(ref).__name__}"
        )

    if ref.startswith("env:"):
        var = ref[len("env:") :]
        try:
            return os.environ[var]
        except KeyError as exc:
            raise SecretResolutionError(
                f"переменная окружения '{var}' не установлена (нужна для '{ref}')"
            ) from exc

    if ref.startswith("file:"):
        path = Path(ref[len("file:") :])
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise SecretResolutionError(
                f"не удалось прочитать файл секрета '{path}': {exc}"
            ) from exc

    if ref.startswith("vault:"):
        raise NotImplementedError(
            "Интеграция с Vault в v0.1 не реализована; используйте env: или file:"
        )

    return ref


def is_reference(value: str) -> bool:
    """Вернуть ``True``, если строка похожа на ссылку на секрет, а не на литерал."""
    return isinstance(value, str) and any(
        value.startswith(prefix) for prefix in ("env:", "file:", "vault:")
    )
