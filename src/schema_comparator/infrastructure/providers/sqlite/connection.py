"""SQLite connection factory using standard library sqlite3."""

import sqlite3
from pathlib import Path
from typing import Any

from schema_comparator.config.models import ConnectionProfile

_IN_MEMORY = ":memory:"


def connect(profile: ConnectionProfile, **kwargs: Any) -> sqlite3.Connection:
    """Open the profile's SQLite database read-only. A missing file raises
    FileNotFoundError instead of letting sqlite3 create an empty one."""
    database_path = profile.connection_string
    if database_path == _IN_MEMORY:
        return sqlite3.connect(database_path, **kwargs)
    path = Path(database_path)
    if not path.is_file():
        raise FileNotFoundError(database_path)
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, **kwargs)
