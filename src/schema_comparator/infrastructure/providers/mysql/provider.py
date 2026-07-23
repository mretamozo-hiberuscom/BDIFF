"""MySQL database provider adapter."""

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.discovery.errors import DiscoveryError
from schema_comparator.domain.capabilities import ProviderCapabilities
from schema_comparator.domain.schema.models import SchemaSnapshot
from schema_comparator.infrastructure.providers.mysql_family import (
    connection,
    introspector,
    profile_parser,
)
from schema_comparator.infrastructure.providers.mysql_family.errors import (
    translate_connect_error,
    translate_query_error,
)


class MySqlProvider:
    """MySQL database provider adapter."""

    provider_id: str = "mysql"

    def validate_profile(self, profile: ConnectionProfile) -> None:
        """Validate MySQL connection profile."""
        profile_parser.validate_mysql_family_profile(profile, provider_name="mysql")

    def capabilities(self, profile: ConnectionProfile | None = None) -> ProviderCapabilities:
        """Return capabilities supported by MySQL."""
        return ProviderCapabilities(
            provider_id="mysql",
            supports_schemas=True,
            supports_transactional_ddl=False,
            supports_drop_column=True,
            supports_alter_column=True,
        )

    def introspect(self, profile: ConnectionProfile) -> SchemaSnapshot:
        """Extract schema snapshot from a live MySQL database."""
        self.validate_profile(profile)
        options = profile_parser.parse_mysql_family_options(profile)

        try:
            with connection.connect(profile, **options) as conn:
                try:
                    with conn.cursor() as cursor:
                        cursor.execute(introspector.MYSQL_FAMILY_CATALOG_QUERY_SQL)
                        rows = cursor.fetchall()
                except Exception as exc:
                    raise translate_query_error(profile.name, exc) from exc
        except DiscoveryError:
            raise
        except Exception as exc:
            raise translate_connect_error(profile.name, exc) from exc

        return introspector.build_snapshot(profile.name, rows, provider_id="mysql")
