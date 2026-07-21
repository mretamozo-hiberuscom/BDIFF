"""SqliteProvider implementation conforming to DatabaseProvider port."""

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.discovery.errors import DiscoveryError
from schema_comparator.domain.capabilities import ProviderCapabilities
from schema_comparator.domain.schema.models import SchemaSnapshot
from schema_comparator.infrastructure.providers.sqlite import (
    connection,
    introspector,
    profile_parser,
)
from schema_comparator.infrastructure.providers.sqlite.errors import (
    translate_connect_error,
    translate_query_error,
)


class SqliteProvider:
    """SQLite database provider adapter."""

    provider_id: str = "sqlite"

    def validate_profile(self, profile: ConnectionProfile) -> None:
        """Validate SQLite profile settings."""
        profile_parser.validate_sqlite_profile(profile)

    def capabilities(self, profile: ConnectionProfile | None = None) -> ProviderCapabilities:
        """Return capabilities supported by SQLite."""
        return ProviderCapabilities(
            provider_id="sqlite",
            supports_schemas=False,
            supports_transactional_ddl=True,
            supports_drop_column=True,
            supports_alter_column=False,
        )

    def introspect(self, profile: ConnectionProfile) -> SchemaSnapshot:
        """Extract schema snapshot from a SQLite database."""
        self.validate_profile(profile)
        options = profile_parser.parse_sqlite_options(profile)

        try:
            conn = connection.connect(profile, **options)
        except Exception as exc:
            raise translate_connect_error(profile.name, exc) from exc

        try:
            snapshot = introspector.introspect_sqlite_schema(conn, profile.name)
        except DiscoveryError:
            raise
        except Exception as exc:
            raise translate_query_error(profile.name, exc) from exc
        finally:
            conn.close()

        return snapshot
