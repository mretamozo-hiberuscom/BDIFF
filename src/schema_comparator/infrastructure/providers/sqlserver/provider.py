"""SqlServerProvider implementation conforming to DatabaseProvider port."""

import pyodbc

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.capabilities import ProviderCapabilities
from schema_comparator.domain.errors import RoutineIntrospectionError
from schema_comparator.domain.schema.models import SchemaSnapshot
from schema_comparator.infrastructure.providers.sqlserver import connection, introspector
from schema_comparator.infrastructure.providers.sqlserver.errors import (
    translate_connect_error,
    translate_query_error,
)


class SqlServerProvider:
    """SQL Server database provider adapter."""

    provider_id: str = "sqlserver"

    def capabilities(self, profile: ConnectionProfile | None = None) -> ProviderCapabilities:
        """Return capabilities supported by SQL Server."""
        return ProviderCapabilities(
            provider_id=self.provider_id,
            supports_schemas=True,
            supports_transactional_ddl=True,
            supports_drop_column=True,
            supports_alter_column=True,
            supports_routine_introspection=True,
            supports_routine_definition=True,
            supports_module_refresh=True,
        )

    def validate_profile(self, profile: ConnectionProfile) -> None:
        """Validate SQL Server profile settings."""
        if not profile.connection_string:
            raise ValueError(f"Profile {profile.name!r} has empty connection string.")

    def introspect(self, profile: ConnectionProfile) -> SchemaSnapshot:
        """Extract schema snapshot from a live SQL Server database."""
        self.validate_profile(profile)
        proc_rows = []
        try:
            with connection.connect(profile) as conn:
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
