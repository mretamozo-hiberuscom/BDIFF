"""PostgreSqlProvider implementation conforming to DatabaseProvider port."""

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.discovery.errors import DiscoveryError
from schema_comparator.domain.capabilities import ProviderCapabilities
from schema_comparator.domain.schema.models import SchemaSnapshot
from schema_comparator.infrastructure.providers.postgresql import (
    connection,
    introspector,
    profile_parser,
)
from schema_comparator.infrastructure.providers.postgresql.errors import (
    translate_connect_error,
    translate_query_error,
)


class PostgreSqlProvider:
    """PostgreSQL database provider adapter."""

    provider_id: str = "postgresql"

    def validate_profile(self, profile: ConnectionProfile) -> None:
        """Validate PostgreSQL profile settings."""
        profile_parser.validate_postgresql_profile(profile)

    def capabilities(self, profile: ConnectionProfile | None = None) -> ProviderCapabilities:
        """Return capabilities supported by PostgreSQL."""
        return ProviderCapabilities(
            provider_id="postgresql",
            supports_schemas=True,
            supports_transactional_ddl=True,
            supports_drop_column=True,
            supports_alter_column=True,
        )

    def introspect(self, profile: ConnectionProfile) -> SchemaSnapshot:
        """Extract schema snapshot from a live PostgreSQL database."""
        self.validate_profile(profile)
        options = profile_parser.parse_postgresql_options(profile)

        try:
            with connection.connect(profile, **options) as conn:
                try:
                    with conn.cursor() as cursor:
                        cursor.execute(introspector.POSTGRESQL_CATALOG_QUERY_SQL)
                        rows = cursor.fetchall()
                except Exception as exc:
                    raise translate_query_error(profile.name, exc) from exc
        except DiscoveryError:
            raise
        except Exception as exc:
            raise translate_connect_error(profile.name, exc) from exc

        return introspector.build_snapshot(profile.name, rows)
