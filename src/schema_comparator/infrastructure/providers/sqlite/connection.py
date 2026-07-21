"""SQLite connection factory using standard library sqlite3."""

import sqlite3
from typing import Any

from schema_comparator.config.models import ConnectionProfile


def connect(profile: ConnectionProfile, **kwargs: Any) -> sqlite3.Connection:
    """Connect to a SQLite database using the standard library sqlite3 module."""
    database_path = profile.connection_string
    return sqlite3.connect(database_path, **kwargs)
