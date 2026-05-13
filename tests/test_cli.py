"""Smoke-тесты Typer-CLI."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from etl_framework.cli import app

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "retail"

runner = CliRunner()


def test_validate_clean_repo():
    result = runner.invoke(app, ["validate", str(EXAMPLES)])
    assert result.exit_code == 0, result.output
    # таблица отчёта содержит русский заголовок «ошибки»
    assert "ошибки" in result.output.lower()


def test_generate_writes_artifacts(tmp_path: Path):
    out = tmp_path / "build"
    result = runner.invoke(app, ["generate", str(EXAMPLES), "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert (out / "pyspark" / "stg_clients.py").is_file()
    assert (out / "pyspark" / "dds_clients.py").is_file()
    assert (out / "airflow" / "etl_stg.py").is_file()
    assert (out / "airflow" / "etl_dds.py").is_file()
    assert (out / ".audit.log").is_file()


def test_generate_with_sql_sinks(tmp_path: Path):
    out = tmp_path / "build"
    result = runner.invoke(
        app, ["generate", str(EXAMPLES), "-o", str(out), "--sql-sinks"]
    )
    assert result.exit_code == 0, result.output
    assert any((out / "sql").rglob("*.sql"))


def test_lineage_export(tmp_path: Path):
    out = tmp_path / "ol.json"
    result = runner.invoke(
        app, ["lineage", "export", str(EXAMPLES), "-o", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert out.is_file()
    assert b"COMPLETE" in out.read_bytes()
