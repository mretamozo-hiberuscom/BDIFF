"""Database provider port interface."""

from typing import Protocol

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.schema.models import SchemaSnapshot


class DatabaseProvider(Protocol):
    """Abstract interface for database schema extraction and capability inspection."""

    provider_id: str

    def validate_profile(self, profile: ConnectionProfile) -> None:
        """Validate connection profile settings for this provider."""
        ...

    def introspect(self, profile: ConnectionProfile) -> SchemaSnapshot:
        """Extract schema snapshot from target database profile."""
        ...
