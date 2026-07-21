"""Oracle database provider adapter."""

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.discovery.errors import DiscoveryError
from schema_comparator.domain.capabilities import ProviderCapabilities
from schema_comparator.domain.schema.models import SchemaSnapshot
from schema_comparator.infrastructure.providers.oracle import (
    connection,
    introspector,
    profile_parser,
)
from schema_comparator.infrastructure.providers.oracle.errors import (
    translate_connect_error,
    translate_query_error,
)


class OracleProvider:
    """Oracle database provider adapter."""

    provider_id: str = "oracle"

    def validate_profile(self, profile: ConnectionProfile) -> None:
        """Validate Oracle connection profile."""
        profile_parser.validate_oracle_profile(profile)

    def capabilities(self, profile: ConnectionProfile | None = None) -> ProviderCapabilities:
        """Return capabilities supported by Oracle."""
        return ProviderCapabilities(
            provider_id="oracle",
            supports_schemas=True,
            supports_transactional_ddl=False,
            supports_drop_column=True,
            supports_alter_column=True,
        )

    def introspect(self, profile: ConnectionProfile) -> SchemaSnapshot:
        """Extract schema snapshot from a live Oracle database."""
        self.validate_profile(profile)
        options = profile_parser.parse_oracle_options(profile)

        try:
            with connection.connect(profile, **options) as conn:
                try:
                    with conn.cursor() as cursor:
                        cursor.execute(introspector.ORACLE_CATALOG_QUERY_SQL)
                        rows = cursor.fetchall()
                except Exception as exc:
                    raise translate_query_error(profile.name, exc) from exc
        except DiscoveryError:
            raise
        except Exception as exc:
            raise translate_connect_error(profile.name, exc) from exc

        return introspector.build_snapshot(profile.name, rows)
