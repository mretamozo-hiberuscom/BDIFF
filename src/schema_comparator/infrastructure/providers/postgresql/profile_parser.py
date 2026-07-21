"""PostgreSQL connection profile and options parser."""

from typing import Any

from schema_comparator.config.models import ConnectionProfile


def validate_postgresql_profile(profile: ConnectionProfile) -> None:
    """Validate PostgreSQL profile connection details and options."""
    if not profile.connection_string:
        raise ValueError(f"Profile {profile.name!r} has empty connection string.")
    if profile.provider and profile.provider.casefold() != "postgresql":
        raise ValueError(
            f"Profile {profile.name!r} has provider {profile.provider!r}, expected 'postgresql'."
        )


def parse_postgresql_options(profile: ConnectionProfile) -> dict[str, Any]:
    """Extract options for PostgreSQL connection, e.g. connect_timeout or SSL mode."""
    options = dict(profile.options or {})
    return options
