"""SqlServerProvider implementation conforming to DatabaseProvider port."""

import pyodbc

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.schema.models import SchemaSnapshot
from schema_comparator.infrastructure.providers.sqlserver import connection, introspector
from schema_comparator.infrastructure.providers.sqlserver.errors import (
    translate_connect_error,
    translate_query_error,
)


class SqlServerProvider:
    """SQL Server database provider adapter."""

    provider_id: str = "sqlserver"

    def validate_profile(self, profile: ConnectionProfile) -> None:
        """Validate SQL Server profile settings."""
        if not profile.connection_string:
            raise ValueError(f"Profile {profile.name!r} has empty connection string.")

    def introspect(self, profile: ConnectionProfile) -> SchemaSnapshot:
        """Extract schema snapshot from a live SQL Server database."""
        self.validate_profile(profile)
        try:
            with connection.connect(profile) as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(introspector.CATALOG_QUERY_SQL)
                    rows = cursor.fetchall()
                except pyodbc.Error as exc:
                    raise translate_query_error(profile.name, exc) from exc
                finally:
                    cursor.close()
        except pyodbc.Error as exc:
            raise translate_connect_error(profile.name, exc) from exc

        return introspector.build_snapshot(profile.name, rows)
