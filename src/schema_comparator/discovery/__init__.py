"""INFORMATION_SCHEMA / sys.* extraction into a schema snapshot model."""

from schema_comparator.discovery.errors import (
    ConnectionFailedError,
    DiscoveryError,
    DriverUnavailableError,
    MetadataAccessError,
)
from schema_comparator.discovery.models import (
    ColumnSnapshot,
    SchemaSnapshot,
    TableSnapshot,
)
from schema_comparator.discovery.service import extract_schema

__all__ = [
    "ColumnSnapshot",
    "TableSnapshot",
    "SchemaSnapshot",
    "extract_schema",
    "DiscoveryError",
    "DriverUnavailableError",
    "ConnectionFailedError",
    "MetadataAccessError",
]
