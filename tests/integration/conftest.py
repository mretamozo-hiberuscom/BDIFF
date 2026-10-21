"""Throwaway SQL Server in Docker for tests that run generated T-SQL.

The `mssql_server` fixture starts a container on first use and removes it
when the session ends. Tests that request it are skipped, never failed,
when Docker is missing, cannot run the Linux image (a Windows runner) or
the `CI` variable is set. Scripts run through the container's own sqlcmd,
the client people use to apply them.
"""

import os
import secrets
import shutil
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

_IMAGE = "mcr.microsoft.com/mssql/server:2022-latest"
_SQLCMD = "/opt/mssql-tools18/bin/sqlcmd"
_READY_TIMEOUT_SECONDS = 120
_SEPARATOR = "\x1f"


class MssqlServer:
    """Runs scripts and queries on the container through sqlcmd."""

    def __init__(self, container: str, password: str) -> None:
        self.container = container
        self._password = password

    def run(
        self, sql: str, *, database: str = "master", stop_on_error: bool = True
    ) -> subprocess.CompletedProcess[str]:
        """Run setup `sql` (UTF-8, `GO` splits batches) from stdin, with
        QUOTED_IDENTIFIER on (`-I`) as filtered indexes and views need."""
        return self._sqlcmd(
            ["-I", "-f", "65001", "-d", database, "-i", "/dev/stdin"],
            stop_on_error=stop_on_error,
            stdin=sql,
        )

    def run_file(
        self, path: Path, *, stop_on_error: bool = True
    ) -> subprocess.CompletedProcess[str]:
        """Run a script file as people do: `sqlcmd -i <file>`, reading it
        with the Windows ANSI code page (1252) unless the file has a BOM.
        With `stop_on_error` sqlcmd exits at the first error (`-b`);
        without it, it keeps going like SSMS does."""
        target = f"/tmp/{secrets.token_hex(6)}.sql"
        copied = subprocess.run(
            ["docker", "cp", str(path), f"{self.container}:{target}"],
            capture_output=True,
            text=True,
        )
        if copied.returncode != 0:
            raise AssertionError(f"docker cp failed: {copied.stderr}")
        return self._sqlcmd(["-f", "1252", "-i", target], stop_on_error=stop_on_error)

    def _sqlcmd(
        self, args: list[str], *, stop_on_error: bool, stdin: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        command = [
            "docker",
            "exec",
            "-i",
            "-e",
            f"SQLCMDPASSWORD={self._password}",
            self.container,
            _SQLCMD,
            "-S",
            "localhost",
            "-U",
            "sa",
            "-C",
            *args,
        ]
        if stop_on_error:
            command.append("-b")
        return subprocess.run(
            command,
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )

    def query(self, sql: str, *, database: str = "master") -> list[tuple[str, ...]]:
        """Rows of a SELECT, every value as text (`NULL` for null)."""
        command = [
            "docker",
            "exec",
            "-e",
            f"SQLCMDPASSWORD={self._password}",
            self.container,
            _SQLCMD,
            "-S",
            "localhost",
            "-U",
            "sa",
            "-C",
            "-f",
            "65001",
            "-b",
            "-d",
            database,
            "-h",
            "-1",
            "-W",
            "-s",
            _SEPARATOR,
            "-Q",
            f"SET NOCOUNT ON; {sql}",
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        if result.returncode != 0:
            raise AssertionError(f"query failed: {result.stdout}{result.stderr}")
        return [
            tuple(line.split(_SEPARATOR))
            for line in result.stdout.splitlines()
            if line.strip()
        ]

    def create_database(self) -> str:
        name = f"bdiff_{secrets.token_hex(4)}"
        self._execute(f"CREATE DATABASE [{name}];")
        return name

    def drop_database(self, name: str) -> None:
        self._execute(
            f"IF DB_ID(N'{name}') IS NOT NULL BEGIN "
            f"ALTER DATABASE [{name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; "
            f"DROP DATABASE [{name}]; END"
        )

    def _execute(self, sql: str) -> None:
        result = self.run(f"{sql}\nGO\n")
        if result.returncode != 0:
            raise AssertionError(f"setup failed: {result.stdout}{result.stderr}")


def _docker_unavailable_reason() -> str | None:
    if os.environ.get("CI"):
        return "CI is set; live SQL Server tests run only locally"
    if shutil.which("docker") is None:
        return "docker not found"
    info = subprocess.run(
        ["docker", "info", "--format", "{{.OSType}}"],
        capture_output=True,
        text=True,
    )
    if info.returncode != 0:
        return "docker daemon not reachable"
    if info.stdout.strip() != "linux":
        return "docker cannot run Linux containers here"
    return None


@pytest.fixture(scope="session")
def mssql_server() -> Iterator[MssqlServer]:
    reason = _docker_unavailable_reason()
    if reason:
        pytest.skip(reason)
    container = f"bdiff-test-mssql-{secrets.token_hex(4)}"
    # Letters, digits and a symbol satisfy the SQL Server password policy.
    password = f"Bd1f_{secrets.token_hex(12)}!"
    started = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            container,
            "-e",
            "ACCEPT_EULA=Y",
            "-e",
            f"MSSQL_SA_PASSWORD={password}",
            "-e",
            "MSSQL_MEMORY_LIMIT_MB=2048",
            _IMAGE,
        ],
        capture_output=True,
        text=True,
    )
    if started.returncode != 0:
        pytest.skip(f"cannot start the SQL Server container: {started.stderr.strip()}")
    try:
        server = MssqlServer(container, password)
        deadline = time.monotonic() + _READY_TIMEOUT_SECONDS
        while True:
            try:
                server.query("SELECT 1")
                break
            except AssertionError:
                if time.monotonic() > deadline:
                    logs = subprocess.run(
                        ["docker", "logs", "--tail", "20", container],
                        capture_output=True,
                        text=True,
                    )
                    pytest.fail(
                        "SQL Server did not answer within "
                        f"{_READY_TIMEOUT_SECONDS} s:\n{logs.stdout}{logs.stderr}"
                    )
                time.sleep(2)
        yield server
    finally:
        subprocess.run(["docker", "rm", "-f", container], capture_output=True)


@pytest.fixture
def mssql_db(mssql_server: MssqlServer) -> Iterator[str]:
    """A fresh, empty database for one test."""
    name = mssql_server.create_database()
    try:
        yield name
    finally:
        mssql_server.drop_database(name)
