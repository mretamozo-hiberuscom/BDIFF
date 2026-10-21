"""pyodbc connection management for SQL Server."""

from contextlib import contextmanager
from typing import Callable, Iterator

import pyodbc

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.infrastructure.providers.sqlserver.profile_parser import (
    has_driver_keyword,
)

DEFAULT_TIMEOUT_SECONDS: float = 30.0

# Used in this order when the connection string names no driver. 17 goes
# first because 18 encrypts by default and would break connections to
# servers with self-signed certificates that work today with 17.
DRIVER_PREFERENCE: tuple[str, ...] = (
    "ODBC Driver 17 for SQL Server",
    "ODBC Driver 18 for SQL Server",
)


def installed_sqlserver_drivers(
    drivers_fn: Callable[[], list[str]] = pyodbc.drivers,
) -> tuple[str, ...]:
    """Names of the installed ODBC drivers for SQL Server."""
    return tuple(driver for driver in drivers_fn() if "SQL Server" in driver)


def with_installed_driver(
    connection_string: str, installed_drivers: tuple[str, ...], *, name: str
) -> str:
    """Prepend the preferred installed driver when the string names none; an
    explicit driver is left as written."""
    if has_driver_keyword(connection_string, name=name):
        return connection_string
    for driver in DRIVER_PREFERENCE:
        if driver in installed_drivers:
            return f"Driver={{{driver}}};{connection_string}"
    return connection_string


@contextmanager
def connect(
    profile: ConnectionProfile,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    connect_fn: Callable[..., "pyodbc.Connection"] = pyodbc.connect,
    drivers_fn: Callable[[], list[str]] = pyodbc.drivers,
) -> Iterator["pyodbc.Connection"]:
    """Yield a short-lived pyodbc connection for a SQL Server `profile`."""
    timeout = int(timeout_seconds)
    connection_string = with_installed_driver(
        profile.connection_string,
        installed_sqlserver_drivers(drivers_fn),
        name=profile.name,
    )
    conn = connect_fn(connection_string, timeout=timeout)
    conn.timeout = timeout
    try:
        yield conn
    finally:
        conn.close()
