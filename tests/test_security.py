"""Tests for the security/secrets module."""

from __future__ import annotations

from pathlib import Path

import pytest

from etl_framework.security import resolve_secret
from etl_framework.security.secrets import SecretResolutionError, is_reference


def test_literal_passthrough():
    assert resolve_secret("plain") == "plain"


def test_env_resolution(monkeypatch):
    monkeypatch.setenv("MY_SECRET", "topsecret")
    assert resolve_secret("env:MY_SECRET") == "topsecret"


def test_env_missing(monkeypatch):
    monkeypatch.delenv("DOES_NOT_EXIST", raising=False)
    with pytest.raises(SecretResolutionError):
        resolve_secret("env:DOES_NOT_EXIST")


def test_file_resolution(tmp_path: Path):
    f = tmp_path / "secret.txt"
    f.write_text("filecreds\n")
    assert resolve_secret(f"file:{f}") == "filecreds"


def test_vault_not_implemented():
    with pytest.raises(NotImplementedError):
        resolve_secret("vault:kv/etlf/db#password")


def test_is_reference():
    assert is_reference("env:X")
    assert is_reference("file:/x")
    assert not is_reference("plain")
