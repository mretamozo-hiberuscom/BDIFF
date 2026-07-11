"""Unit tests for tui.formatting: pure tree-building, filter-matching,
detail/header text derived from a ComparisonResult (no Textual imports)."""

from report.conftest import comparison_result_empty, comparison_result_with_findings

from schema_comparator.compare.models import (
    ColumnAttributes,
    ColumnMismatch,
    MissingColumn,
    MissingTable,
)
from schema_comparator.report.console import _TYPE_LABELS
from schema_comparator.tui.formatting import (
    build_tree_data,
    detail_text,
    entry_matches,
    header_counts,
    header_text,
    leaf_label,
)


def test_build_tree_data_groups_by_qualified_table_name() -> None:
    tree_data = build_tree_data(comparison_result_with_findings())

    labels = [group.qualified_label for group in tree_data.groups]

    assert labels == ["sales.Invoice", "sales.Payment"]


def test_build_tree_data_returns_empty_groups_for_empty_result() -> None:
    tree_data = build_tree_data(comparison_result_empty())

    assert tree_data.groups == ()


def test_leaf_label_matches_console_missing_table_wording() -> None:
    entry = MissingTable(
        schema_name="sales", table_name="Payment", missing_from_profile="c"
    )

    assert leaf_label(entry) == "tabla faltante (de c)"


def test_leaf_label_matches_console_missing_column_wording() -> None:
    entry = MissingColumn(
        schema_name="sales",
        table_name="Invoice",
        column_name="notes",
        missing_from_profile="c",
    )

    assert leaf_label(entry) == "notes: columna faltante (de c)"


def test_leaf_label_matches_console_column_mismatch_wording() -> None:
    entry = ColumnMismatch(
        schema_name="sales",
        table_name="Invoice",
        column_name="amount",
        values_by_profile=(
            ("a", ColumnAttributes("decimal", None, 10, 2, False)),
            ("b", ColumnAttributes("decimal", None, 12, 2, False)),
        ),
    )

    assert leaf_label(entry) == "amount: discrepancia de atributos entre a, b"


def test_detail_text_for_column_mismatch_lists_all_profiles_and_attributes() -> None:
    entry = ColumnMismatch(
        schema_name="sales",
        table_name="Invoice",
        column_name="amount",
        values_by_profile=(
            ("a", ColumnAttributes("decimal", None, 10, 2, False)),
            ("b", ColumnAttributes("decimal", None, 12, 2, False)),
        ),
    )

    text = detail_text(entry)

    assert "a: decimal(10,2), NOT NULL" in text
    assert "b: decimal(12,2), NOT NULL" in text


def test_detail_text_for_missing_table_shows_missing_from_profile() -> None:
    entry = MissingTable(
        schema_name="sales", table_name="Payment", missing_from_profile="b"
    )

    text = detail_text(entry)

    assert "sales.Payment" in text
    assert "faltante en el perfil 'b'" in text


def test_detail_text_for_missing_column_shows_missing_from_profile() -> None:
    entry = MissingColumn(
        schema_name="sales",
        table_name="Invoice",
        column_name="notes",
        missing_from_profile="a",
    )

    text = detail_text(entry)

    assert "sales.Invoice.notes" in text
    assert "Faltante en el perfil 'a'" in text


def test_detail_text_never_renders_values_by_profile_for_missing_entries() -> None:
    table_entry = MissingTable(
        schema_name="sales", table_name="Payment", missing_from_profile="b"
    )
    column_entry = MissingColumn(
        schema_name="sales",
        table_name="Invoice",
        column_name="notes",
        missing_from_profile="a",
    )

    assert "values_by_profile" not in detail_text(table_entry)
    assert "values_by_profile" not in detail_text(column_entry)


def test_header_counts_match_console_type_labels_mapping() -> None:
    result = comparison_result_with_findings()

    counts = header_counts(result)

    assert set(counts.keys()) == set(_TYPE_LABELS.keys())
    assert counts[MissingTable] == 1
    assert counts[MissingColumn] == 1
    assert counts[ColumnMismatch] == 1


def test_header_text_lists_compared_profiles() -> None:
    result = comparison_result_with_findings()

    text = header_text(result)

    assert "a, b, c" in text


def test_entry_matches_by_diff_type_label() -> None:
    entry = ColumnMismatch(
        schema_name="sales",
        table_name="Invoice",
        column_name="amount",
        values_by_profile=(("a", ColumnAttributes("decimal", None, 10, 2, False)),),
    )

    assert entry_matches(entry, "ColumnMismatch") is True
    assert entry_matches(entry, "MissingTable") is False


def test_entry_matches_by_table_name() -> None:
    entry = MissingTable(
        schema_name="sales", table_name="Payment", missing_from_profile="c"
    )

    assert entry_matches(entry, "Payment") is True
    assert entry_matches(entry, "Invoice") is False


def test_entry_matches_by_column_name() -> None:
    entry = MissingColumn(
        schema_name="sales",
        table_name="Invoice",
        column_name="notes",
        missing_from_profile="c",
    )

    assert entry_matches(entry, "notes") is True
    assert entry_matches(entry, "amount") is False


def test_entry_matches_is_case_insensitive() -> None:
    entry = MissingTable(
        schema_name="sales", table_name="Payment", missing_from_profile="c"
    )

    assert entry_matches(entry, "PAYMENT") is True


def test_entry_matches_returns_true_for_empty_filter_text() -> None:
    entry = MissingTable(
        schema_name="sales", table_name="Payment", missing_from_profile="c"
    )

    assert entry_matches(entry, "") is True
