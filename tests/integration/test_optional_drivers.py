"""Without pyodbc (Linux/macOS without unixODBC) the CLI still runs every
other provider; only a SQL Server profile needs the driver (ADR 0002)."""

import os
import sqlite3
import subprocess
import sys
import textwrap
from pathlib import Path

_BLOCK_PYODBC_AND_RUN_CLI = textwrap.dedent(
    """
    import sys
    sys.modules["pyodbc"] = None  # makes `import pyodbc` raise ImportError
    from schema_comparator.cli import main
    sys.exit(main(sys.argv[1:]))
    """
)


def _sqlite_db(path: Path, ddl: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(ddl)


def _run_cli(tmp_path: Path, config: str) -> subprocess.CompletedProcess:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-c", _BLOCK_PYODBC_AND_RUN_CLI, "--config", str(config_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        # The CLI writes in the console code page (cp1252 on Windows when
        # redirected); pin the child's encoding so the output decodes.
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        timeout=120,
    )


def test_sqlite_profiles_compare_without_pyodbc(tmp_path: Path) -> None:
    _sqlite_db(tmp_path / "a.db", "CREATE TABLE poliza (id INTEGER, prima REAL)")
    _sqlite_db(tmp_path / "b.db", "CREATE TABLE poliza (id INTEGER)")

    completed = _run_cli(
        tmp_path,
        f"""
profiles:
  a:
    provider: sqlite
    connection_string: "{(tmp_path / "a.db").as_posix()}"
  b:
    provider: sqlite
    connection_string: "{(tmp_path / "b.db").as_posix()}"
""",
    )

    assert completed.returncode == 1, completed.stderr
    assert "Columnas faltantes: 1" in completed.stdout


def test_sqlserver_profile_without_pyodbc_reports_missing_driver(
    tmp_path: Path,
) -> None:
    completed = _run_cli(
        tmp_path,
        """
profiles:
  a:
    provider: sqlserver
    connection_string: "Server=srv;Database=A;Trusted_Connection=yes;"
  b:
    provider: sqlserver
    connection_string: "Server=srv;Database=B;Trusted_Connection=yes;"
""",
    )

    assert completed.returncode == 2
    assert "sqlserver" in completed.stderr
    assert "Traceback" not in completed.stderr
