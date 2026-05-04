"""Secret-reference resolution.

A *secret reference* is a string with one of the following shapes:

* ``env:NAME`` — read from the environment variable ``NAME``;
* ``file:/path/to/file`` — read the (single-line) file contents;
* ``vault:path/to/secret#field`` — placeholder; raises ``NotImplementedError``;
* anything else — returned verbatim, treated as a literal value.

Generated PySpark code never embeds the literal secret. Instead, it embeds the
**reference** and resolves it at runtime using the same function. This keeps
secrets out of the generated artifacts and out of git.
"""

from __future__ import annotations

import os
from pathlib import Path


class SecretResolutionError(Exception):
    """Raised when a secret reference cannot be resolved."""


def resolve_secret(ref: str) -> str:
    """Resolve a secret reference at runtime.

    The function is deliberately permissive: literal values (anything without a
    ``scheme:`` prefix) pass through, so author-time examples can use plain
    placeholders.
    """
    if not isinstance(ref, str):
        raise SecretResolutionError(f"secret reference must be a string, got {type(ref).__name__}")

    if ref.startswith("env:"):
        var = ref[len("env:") :]
        try:
            return os.environ[var]
        except KeyError as exc:
            raise SecretResolutionError(
                f"environment variable '{var}' is not set (required by '{ref}')"
            ) from exc

    if ref.startswith("file:"):
        path = Path(ref[len("file:") :])
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise SecretResolutionError(f"cannot read secret file '{path}': {exc}") from exc

    if ref.startswith("vault:"):
        raise NotImplementedError(
            "Vault integration is not implemented in v0.1; use env: or file: for now"
        )

    return ref


def is_reference(value: str) -> bool:
    """Return ``True`` if the string looks like a secret reference (not a literal)."""
    return isinstance(value, str) and any(
        value.startswith(prefix) for prefix in ("env:", "file:", "vault:")
    )
