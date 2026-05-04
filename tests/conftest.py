"""Shared fixtures for the test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from etl_framework.repository import MetadataRepository

EXAMPLES_ROOT = Path(__file__).resolve().parents[1] / "examples" / "retail"


@pytest.fixture
def retail_repo() -> MetadataRepository:
    repo = MetadataRepository(EXAMPLES_ROOT)
    repo.load()
    return repo
