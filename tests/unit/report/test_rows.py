"""Unit tests for report.rows: grouped_rows_by_table row-merging."""

from schema_comparator.compare.models import (
    ColumnAttributes,
    ColumnMismatch,
    ComparisonResult,
    MissingColumn,
    MissingTable,
)
from schema_comparator.report.rows import grouped_rows_by_table


def test_missing_table_siblings_across_profiles_merge_into_one_row() -> None:
    result = ComparisonResult(
        compared_profiles=("a", "b", "c"),
        entries=(
            MissingTable(schema_name="dbo", table_name="Productos", missing_from_profile="b"),
            MissingTable(schema_name="dbo", table_name="Productos", missing_from_profile="c"),
        ),
    )

    tables = grouped_rows_by_table(result)

    assert len(tables) == 1
    (identity, rows) = tables[0]
    assert identity == ("dbo", "Productos")
    assert len(rows) == 1
    assert [e.missing_from_profile for e in rows[0]] == ["b", "c"]


def test_missing_column_siblings_for_same_column_merge_into_one_row() -> None:
    result = ComparisonResult(
        compared_profiles=("a", "b", "c"),
        entries=(
            MissingColumn(
                schema_name="dbo", table_name="Productos", column_name="notes",
                missing_from_profile="b",
            ),
            MissingColumn(
                schema_name="dbo", table_name="Productos", column_name="notes",
                missing_from_profile="c",
            ),
        ),
    )

    _, rows = grouped_rows_by_table(result)[0]

    assert len(rows) == 1
    assert [e.missing_from_profile for e in rows[0]] == ["b", "c"]


def test_different_columns_never_merge_into_the_same_row() -> None:
    result = ComparisonResult(
        compared_profiles=("a", "b"),
        entries=(
            MissingColumn(
                schema_name="dbo", table_name="Productos", column_name="amount",
                missing_from_profile="b",
            ),
            MissingColumn(
                schema_name="dbo", table_name="Productos", column_name="notes",
                missing_from_profile="b",
            ),
        ),
    )

    _, rows = grouped_rows_by_table(result)[0]

    assert len(rows) == 2
    assert [e.column_name for group in rows for e in group] == ["amount", "notes"]


def test_missing_column_and_column_mismatch_stay_separate_rows() -> None:
    attrs = ColumnAttributes("decimal", None, 10, 2, False)
    result = ComparisonResult(
        compared_profiles=("a", "b", "c"),
        entries=(
            MissingColumn(
                schema_name="dbo", table_name="Productos", column_name="amount",
                missing_from_profile="c",
                present_attributes=(("a", attrs), ("b", attrs)),
            ),
            ColumnMismatch(
                schema_name="dbo", table_name="Productos", column_name="amount",
                values_by_profile=(("a", attrs), ("b", attrs)),
            ),
        ),
    )

    _, rows = grouped_rows_by_table(result)[0]

    assert len(rows) == 2
    assert [type(group[0]).__name__ for group in rows] == ["MissingColumn", "ColumnMismatch"]


def test_different_tables_are_separate_groups() -> None:
    result = ComparisonResult(
        compared_profiles=("a", "b"),
        entries=(
            MissingTable(schema_name="dbo", table_name="Alpha", missing_from_profile="b"),
            MissingTable(schema_name="dbo", table_name="Beta", missing_from_profile="b"),
        ),
    )

    tables = grouped_rows_by_table(result)

    assert [identity for identity, _ in tables] == [("dbo", "Alpha"), ("dbo", "Beta")]
