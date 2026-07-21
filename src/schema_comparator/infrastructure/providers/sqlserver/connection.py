"""pyodbc connection management for SQL Server."""

from contextlib import contextmanager
from typing import Callable, Iterator

import pyodbc

from schema_comparator.config.models import ConnectionProfile

DEFAULT_TIMEOUT_SECONDS: float = 30.0


@contextmanager
def connect(
    profile: ConnectionProfile,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    connect_fn: Callable[..., "pyodbc.Connection"] = pyodbc.connect,
) -> Iterator["pyodbc.Connection"]:
    """Yield a short-lived pyodbc connection for a SQL Server `profile`."""
    timeout = int(timeout_seconds)
    conn = connect_fn(profile.connection_string, timeout=timeout)
    conn.timeout = timeout
    try:
        yield conn
    finally:
        conn.close()
