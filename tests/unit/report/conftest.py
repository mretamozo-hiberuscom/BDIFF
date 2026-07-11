"""Shared ComparisonResult builders for report-rendering unit tests.

Plain factory functions (not pytest fixtures), matching the convention
already used by `compare/conftest.py` and `discovery/conftest.py`.
"""

from schema_comparator.compare.models import (
    ColumnAttributes,
    ColumnMismatch,
    ComparisonResult,
    MissingColumn,
    MissingTable,
)


def comparison_result_with_findings() -> ComparisonResult:
    """A 3-profile result exercising all three DiffEntry variants across
    two tables, already ordered as `compare.engine.compare_snapshots`
    would produce it (qualified table identity, then MissingTable <
    MissingColumn < ColumnMismatch, then column name ascending)."""
    return ComparisonResult(
        compared_profiles=("a", "b", "c"),
        entries=(
            MissingColumn(
                schema_name="sales",
                table_name="Invoice",
                column_name="notes",
                missing_from_profile="c",
                present_attributes=(
                    (
                        "a",
                        ColumnAttributes(
                            data_type="varchar",
                            character_maximum_length=255,
                            numeric_precision=None,
                            numeric_scale=None,
                            is_nullable=True,
                        ),
                    ),
                    (
                        "b",
                        ColumnAttributes(
                            data_type="varchar",
                            character_maximum_length=255,
                            numeric_precision=None,
                            numeric_scale=None,
                            is_nullable=True,
                        ),
                    ),
                ),
            ),
            ColumnMismatch(
                schema_name="sales",
                table_name="Invoice",
                column_name="amount",
                values_by_profile=(
                    (
                        "a",
                        ColumnAttributes(
                            data_type="decimal",
                            character_maximum_length=None,
                            numeric_precision=10,
                            numeric_scale=2,
                            is_nullable=False,
                        ),
                    ),
                    (
                        "b",
                        ColumnAttributes(
                            data_type="decimal",
                            character_maximum_length=None,
                            numeric_precision=12,
                            numeric_scale=2,
                            is_nullable=False,
                        ),
                    ),
                ),
            ),
            MissingTable(
                schema_name="sales",
                table_name="Payment",
                missing_from_profile="c",
            ),
        ),
    )


def comparison_result_empty() -> ComparisonResult:
    """A clean-comparison result: named profiles, no findings."""
    return ComparisonResult(compared_profiles=("a", "b"), entries=())
