"""N-way diff engine over schema snapshots (union-of-objects baseline)."""

from schema_comparator.compare.engine import compare_snapshots
from schema_comparator.compare.errors import (
    ComparisonError,
    DuplicateProfileNameError,
    InsufficientSnapshotsError,
)
from schema_comparator.compare.models import (
    ColumnAttributes,
    ColumnMismatch,
    ComparisonResult,
    MissingColumn,
    MissingTable,
)

__all__ = [
    "ColumnAttributes",
    "ColumnMismatch",
    "ComparisonResult",
    "MissingColumn",
    "MissingTable",
    "compare_snapshots",
    "ComparisonError",
    "InsufficientSnapshotsError",
    "DuplicateProfileNameError",
]

