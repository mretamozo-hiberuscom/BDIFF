"""SchemaExtractionService: Centralized extraction via ProviderRegistry."""

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.schema.models import SchemaSnapshot
from schema_comparator.infrastructure.providers import ProviderRegistry, get_default_registry


class SchemaExtractionService:
    """Service orchestrating schema extraction using the registered DatabaseProvider for each profile."""

    def __init__(self, registry: ProviderRegistry | None = None) -> None:
        self._registry = registry or get_default_registry()

    def extract(self, profile: ConnectionProfile) -> SchemaSnapshot:
        """Extract a full SchemaSnapshot by dispatching to the matching provider in registry."""
        provider = self._registry.require(profile.provider)
        provider.validate_profile(profile)
        return provider.introspect(profile)


def default_extract_schema(profile: ConnectionProfile) -> SchemaSnapshot:
    """Default function matching extractor Callable signature, backed by ProviderRegistry."""
    service = SchemaExtractionService()
    return service.extract(profile)
