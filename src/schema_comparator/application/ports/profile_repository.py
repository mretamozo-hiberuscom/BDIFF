"""Profile repository port interface."""

from typing import Protocol

from schema_comparator.config.models import ConnectionProfile


class ProfileRepository(Protocol):
    """Abstract interface for loading and storing connection profiles."""

    def load_profiles(self, path_or_source: str) -> list[ConnectionProfile]:
        """Load connection profiles from specified source."""
        ...
