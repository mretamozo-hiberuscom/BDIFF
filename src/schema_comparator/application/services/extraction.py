"""SchemaExtractionService: Centralized extraction via ProviderRegistry."""

from typing import TYPE_CHECKING
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.schema.models import SchemaSnapshot

if TYPE_CHECKING:
    from schema_comparator.infrastructure.providers.registry import ProviderRegistry


class SchemaExtractionService:
    """Service orchestrating schema extraction using the registered DatabaseProvider for each profile."""

    def __init__(self, registry: "ProviderRegistry | None" = None) -> None:
        if registry is None:
            from schema_comparator.infrastructure.providers.registry import get_default_registry
            registry = get_default_registry()
        self._registry = registry

    def extract(self, profile: ConnectionProfile) -> SchemaSnapshot:
        """Extract a full SchemaSnapshot by dispatching to the matching provider in registry."""
        provider = self._registry.require(profile.provider)
        provider.validate_profile(profile)
        return provider.introspect(profile)


def default_extract_schema(profile: ConnectionProfile) -> SchemaSnapshot:
    """Default function matching extractor Callable signature, backed by ProviderRegistry."""
    service = SchemaExtractionService()
    return service.extract(profile)
