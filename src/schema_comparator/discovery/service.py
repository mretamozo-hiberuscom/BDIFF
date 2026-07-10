"""Extraction orchestration: connect, query the catalog, normalize."""

from typing import Callable

import pyodbc

from schema_comparator import connectors
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.connectors import DEFAULT_TIMEOUT_SECONDS
from schema_comparator.discovery.errors import (
    translate_connect_error,
    translate_query_error,
)
from schema_comparator.discovery.models import SchemaSnapshot
from schema_comparator.discovery.queries import CATALOG_QUERY_SQL, _build_snapshot


def extract_schema(
    profile: ConnectionProfile,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    connect_fn: Callable[..., "pyodbc.Connection"] = pyodbc.connect,
) -> SchemaSnapshot:
    """Extract a read-only, in-memory `SchemaSnapshot` for `profile`.

    Uses a short-lived connection (see `connectors.connect`) to run the
    single catalog query, releasing all resources before returning or
    raising. Connect-phase and query-phase `pyodbc.Error`s are translated
    into profile-safe `DiscoveryError` subclasses; raw driver text never
    reaches the caller.
    """
    try:
        with connectors.connect(
            profile, timeout_seconds=timeout_seconds, connect_fn=connect_fn
        ) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(CATALOG_QUERY_SQL)
                rows = cursor.fetchall()
            except pyodbc.Error as exc:
                raise translate_query_error(profile.name, exc) from exc
            finally:
                cursor.close()
    except pyodbc.Error as exc:
        raise translate_connect_error(profile.name, exc) from exc

    return _build_snapshot(profile.name, rows)
