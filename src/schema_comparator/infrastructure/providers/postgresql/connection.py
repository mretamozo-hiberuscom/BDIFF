"""PostgreSQL connection factory using psycopg."""

from typing import Any

from schema_comparator.config.models import ConnectionProfile


def connect(profile: ConnectionProfile, **kwargs: Any) -> Any:
    """Connect to a PostgreSQL database using psycopg.

    Raises ImportError if psycopg is not installed.
    """
    import psycopg

    conn_str = profile.connection_string
    return psycopg.connect(conn_str, **kwargs)
