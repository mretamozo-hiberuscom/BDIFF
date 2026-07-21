"""Result and diff-entry models for N-way schema comparison.

Re-exported from domain.comparison.models for backward compatibility.
"""

from schema_comparator.domain.comparison.models import (
    ColumnAttributes,
    ColumnMismatch,
    ComparisonResult,
    DiffEntry,
    ForeignKeyMismatch,
    IndexMismatch,
    MissingColumn,
    MissingTable,
    NamedColumnAttributes,
    PrimaryKeyMismatch,
)

__all__ = [
    "ColumnAttributes",
    "ColumnMismatch",
    "ComparisonResult",
    "DiffEntry",
    "ForeignKeyMismatch",
    "IndexMismatch",
    "MissingColumn",
    "MissingTable",
    "NamedColumnAttributes",
    "PrimaryKeyMismatch",
]
