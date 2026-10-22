"""Unit tests for tui.formatting: pure tree-building, filter-matching,
detail/header text derived from a ComparisonResult (no Textual imports)."""

from report.conftest import comparison_result_empty, comparison_result_with_findings
from rich.text import Text

from schema_comparator.compare.models import (
    ColumnAttributes,
    ColumnMismatch,
    ComparisonResult,
    MissingColumn,
    MissingTable,
)
from schema_comparator.report.console import _TYPE_LABELS
from schema_comparator.tui.formatting import (
    build_tree_data,
    detail_markup,
    detail_text,
    entry_matches,
    group_markup,
    header_counts,
    header_text,
    leaf_label,
    leaf_parts,
    profiles_markup,
    summary_markup,
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


def _mismatch(*values: tuple[str, ColumnAttributes]) -> ColumnMismatch:
    return ColumnMismatch(
        schema_name="sales",
        table_name="Invoice",
        column_name="amount",
        values_by_profile=values,
    )


def test_summary_markup_has_one_chip_per_kind_with_a_count() -> None:
    markup = summary_markup(comparison_result_with_findings())

    assert "1 tabla faltante" in markup
    assert "1 columna faltante" in markup
    assert "1 discrepancia de columna" in markup
    assert "3 hallazgos en 2 objetos" in markup
    assert "rutina" not in markup


def test_summary_markup_pluralises_counts() -> None:
    result = ComparisonResult(
        compared_profiles=("a", "b"),
        entries=(
            MissingTable("s", "T1", "b"),
            MissingTable("s", "T2", "b"),
        ),
    )

    assert "2 tablas faltantes" in summary_markup(result)


def test_summary_markup_reports_all_clear_without_findings() -> None:
    assert "Sin diferencias" in summary_markup(comparison_result_empty())


def test_profiles_markup_lists_profiles_and_escapes_brackets() -> None:
    result = ComparisonResult(compared_profiles=("dev[red]", "qa"), entries=())

    assert profiles_markup(result) == "2 perfiles: dev\\[red] · qa"


def test_detail_markup_merges_profiles_that_share_a_definition() -> None:
    same = ColumnAttributes("decimal", None, 10, 2, False)
    other = ColumnAttributes("decimal", None, 12, 2, False)

    markup = detail_markup(_mismatch(("a", same), ("b", other), ("c", same)))

    assert "a, c:" in markup
    assert "[green]decimal(10,2), NOT NULL[/]" in markup
    assert "Definiciones distintas (2)" in markup


def test_detail_markup_for_missing_table_counts_columns_per_profile() -> None:
    entry = MissingTable(
        schema_name="sales",
        table_name="Payment",
        missing_from_profile="c",
        present_columns=(
            ("a", ()),
            ("b", ()),
        ),
    )

    markup = detail_markup(entry)

    assert "Falta en" in markup
    assert "a, b:" in markup
    assert "0 columnas" in markup


def test_detail_markup_never_reads_identifiers_as_markup() -> None:
    attrs = ColumnAttributes("int", None, None, None, False)
    entry = ColumnMismatch(
        schema_name="dbo",
        table_name="[/bold]T",
        column_name="x[red]",
        values_by_profile=(("dev[1]", attrs), ("qa", attrs)),
    )

    plain = Text.from_markup(detail_markup(entry)).plain

    assert "[/bold]T" in plain
    assert "x[red]" in plain
    assert "dev[1], qa:" in plain


def test_group_markup_lists_every_finding_of_the_table() -> None:
    group = build_tree_data(comparison_result_with_findings()).groups[0]

    plain = Text.from_markup(group_markup(group)).plain

    assert plain.startswith("sales.Invoice\n2 hallazgos")
    assert "notes: columna faltante (de c)" in plain
    assert "amount: discrepancia de atributos entre a, b" in plain


def test_leaf_parts_joined_equal_leaf_label() -> None:
    for entry in comparison_result_with_findings().entries:
        subject, description = leaf_parts(entry)
        expected = f"{subject}: {description}" if subject else description
        assert leaf_label(entry) == expected
