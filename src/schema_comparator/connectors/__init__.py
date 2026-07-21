"""pyodbc connection management per profile.

Re-exported from infrastructure.providers.sqlserver.connection for backward compatibility.
"""

from schema_comparator.infrastructure.providers.sqlserver.connection import (
    DEFAULT_TIMEOUT_SECONDS,
    connect,
)

__all__ = ["DEFAULT_TIMEOUT_SECONDS", "connect"]
