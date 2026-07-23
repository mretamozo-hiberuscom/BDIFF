"""Extraction orchestration: connect, query the catalog, normalize."""

from typing import Any, Callable

import pyodbc

from schema_comparator.application.services.extraction import (
    SchemaExtractionService,
    default_extract_schema,
)
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.schema.models import SchemaSnapshot


def extract_schema(
    profile: ConnectionProfile,
    *,
    timeout_seconds: float = 30.0,
    connect_fn: Callable[..., Any] | None = None,
) -> SchemaSnapshot:
    """Extract a read-only, in-memory SchemaSnapshot for profile including tables and procedures."""
    if connect_fn is not None:
        from schema_comparator.domain.errors import RoutineIntrospectionError
        from schema_comparator.infrastructure.providers.sqlserver import connection, introspector
        from schema_comparator.infrastructure.providers.sqlserver.errors import (
            translate_connect_error,
            translate_query_error,
        )

        proc_rows = []
        try:
            with connection.connect(
                profile, timeout_seconds=timeout_seconds, connect_fn=connect_fn
            ) as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(introspector.CATALOG_QUERY_SQL)
                    rows = cursor.fetchall()
                    try:
                        cursor.execute(introspector.PROCEDURES_QUERY_SQL)
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

        return introspector.build_snapshot(profile.name, rows, proc_rows=proc_rows)

    return default_extract_schema(profile)
