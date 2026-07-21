"""SQL Server error translation from pyodbc exceptions to domain discovery errors."""

from schema_comparator.discovery.errors import (
    translate_connect_error,
    translate_query_error,
)

__all__ = ["translate_connect_error", "translate_query_error"]
