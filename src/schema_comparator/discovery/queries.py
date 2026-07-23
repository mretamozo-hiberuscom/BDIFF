"""INFORMATION_SCHEMA catalog query text and row normalization.

Re-exported from infrastructure.providers.sqlserver.introspector for backward compatibility.
"""

from schema_comparator.infrastructure.providers.sqlserver.introspector import (
    CATALOG_QUERY_SQL,
    PROCEDURES_QUERY_SQL,
    _build_snapshot,
)

__all__ = ["CATALOG_QUERY_SQL", "PROCEDURES_QUERY_SQL", "_build_snapshot"]
