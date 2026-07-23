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
from schema_comparator.discovery.queries import CATALOG_QUERY_SQL, PROCEDURES_QUERY_SQL, _build_snapshot
from schema_comparator.domain.errors import RoutineIntrospectionError


def extract_schema(
    profile: ConnectionProfile,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    connect_fn: Callable[..., "pyodbc.Connection"] = pyodbc.connect,
) -> SchemaSnapshot:
    """Extract a read-only, in-memory `SchemaSnapshot` for `profile` including tables and procedures."""
    proc_rows = []
    try:
        with connectors.connect(
            profile, timeout_seconds=timeout_seconds, connect_fn=connect_fn
        ) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(CATALOG_QUERY_SQL)
                rows = cursor.fetchall()
                try:
                    cursor.execute(PROCEDURES_QUERY_SQL)
                    proc_rows = cursor.fetchall()
                except pyodbc.Error as exc:
                    raise RoutineIntrospectionError(
                        f"No se pudieron extraer los procedimientos del perfil {profile.name!r}"
                    ) from exc
            except pyodbc.Error as exc:
                if not isinstance(exc, RoutineIntrospectionError):
                    raise translate_query_error(profile.name, exc) from exc
                raise
            finally:
                cursor.close()
    except pyodbc.Error as exc:
        raise translate_connect_error(profile.name, exc) from exc

    return _build_snapshot(profile.name, rows, proc_rows=proc_rows)
