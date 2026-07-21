"""SQLite connection profile and options parser."""

from typing import Any

from schema_comparator.config.models import ConnectionProfile


def validate_sqlite_profile(profile: ConnectionProfile) -> None:
    """Validate SQLite profile connection details and options."""
    if not profile.connection_string:
        raise ValueError(f"Profile {profile.name!r} has empty connection string.")
    if profile.provider and profile.provider.casefold() != "sqlite":
        raise ValueError(
            f"Profile {profile.name!r} has provider {profile.provider!r}, expected 'sqlite'."
        )


def parse_sqlite_options(profile: ConnectionProfile) -> dict[str, Any]:
    """Extract connection parameters/options for SQLite."""
    options = dict(profile.options or {})
    return options
