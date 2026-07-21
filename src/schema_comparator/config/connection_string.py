"""Translate ADO.NET/`SqlClient`-style connection-string keywords to ODBC form.

Re-exported from infrastructure.providers.sqlserver.profile_parser for backward compatibility.
"""

from schema_comparator.infrastructure.providers.sqlserver.profile_parser import (
    _split_token,
    _tokenize,
    translate,
)

__all__ = ["translate", "_tokenize", "_split_token"]
