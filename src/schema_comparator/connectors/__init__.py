"""pyodbc connection management per profile."""

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
    """Yield a short-lived pyodbc connection for `profile`.

    This is the only call site for `connect_fn` (defaults to the real
    `pyodbc.connect`) in the whole package. The login timeout and the
    query timeout share the same `timeout_seconds` value: the former is
    passed to `connect_fn`, the latter is applied via `connection.timeout`
    immediately after a successful connect. Both `pyodbc.connect`'s
    `timeout` kwarg and `connection.timeout`'s setter require a plain int
    (a float raises `TypeError: 'float' object cannot be interpreted as
    an integer` either way), so `timeout_seconds` is cast to `int` once
    and that same int is used for both. The connection is always closed
    before this context manager exits, whether or not the caller's block
    raised.

    Driver errors (`pyodbc.Error`) are intentionally left untranslated here
    and propagate unchanged to the caller; translation into domain errors
    is `discovery`'s responsibility, not this connection boundary's.
    """
    timeout = int(timeout_seconds)
    conn = connect_fn(profile.connection_string, timeout=timeout)
    conn.timeout = timeout
    try:
        yield conn
    finally:
        conn.close()
