"""Unit tests for compare.engine: union, missing-table detection, ordering."""

from schema_comparator.compare.engine import compare_snapshots
from schema_comparator.compare.models import (
    ColumnAttributes,
    ColumnMismatch,
    MissingColumn,
    MissingTable,
)
from compare.conftest import make_column, make_snapshot, make_snapshot_with_tables, make_table


def test_valid_multi_profile_input_is_accepted() -> None:
    a = make_snapshot("a", ("sales", "Invoice"))
    b = make_snapshot("b", ("sales", "Invoice"))
    c = make_snapshot("c", ("sales", "Invoice"))

    result = compare_snapshots([a, b, c])

    assert result.compared_profiles == ("a", "b", "c")


def test_union_includes_tables_from_every_snapshot() -> None:
    a = make_snapshot("a", ("sales", "Invoice"))
    b = make_snapshot("b", ("sales", "Invoice"), ("sales", "Payment"))
    c = make_snapshot("c", ("archive", "Invoice"))

    result = compare_snapshots([a, b, c])

    identities = {entry.qualified_name for entry in result.entries}
    assert identities == {
        ("sales", "Invoice"),
        ("sales", "Payment"),
        ("archive", "Invoice"),
    }


def test_union_result_ordering_is_independent_of_input_order() -> None:
    a = make_snapshot("a", ("sales", "Invoice"), ("sales", "Payment"))
    b = make_snapshot("b", ("sales", "Invoice"))

    result_ab = compare_snapshots([a, b])
    result_ba = compare_snapshots([b, a])

    assert result_ab.entries == result_ba.entries
    assert result_ab.compared_profiles == result_ba.compared_profiles


def test_table_missing_from_one_of_three_profiles() -> None:
    a = make_snapshot("a", ("sales", "Payment"))
    b = make_snapshot("b", ("sales", "Payment"))
    c = make_snapshot("c")

    result = compare_snapshots([a, b, c])

    assert result.entries == (
        MissingTable(
            schema_name="sales", table_name="Payment", missing_from_profile="c"
        ),
    )


def test_table_missing_from_multiple_profiles() -> None:
    a = make_snapshot("a", ("archive", "Invoice"))
    b = make_snapshot("b")
    c = make_snapshot("c")

    result = compare_snapshots([a, b, c])

    assert result.entries == (
        MissingTable(
            schema_name="archive",
            table_name="Invoice",
            missing_from_profile="b",
        ),
        MissingTable(
            schema_name="archive",
            table_name="Invoice",
            missing_from_profile="c",
        ),
    )


def test_table_present_everywhere_produces_no_entry() -> None:
    a = make_snapshot("a", ("sales", "Invoice"))
    b = make_snapshot("b", ("sales", "Invoice"))

    result = compare_snapshots([a, b])

    assert not any(
        entry.qualified_name == ("sales", "Invoice") for entry in result.entries
    )


def test_entries_are_ordered_by_ascending_qualified_table_identity() -> None:
    a = make_snapshot("a", ("zeta", "Report"), ("alpha", "Customer"))
    b = make_snapshot("b")

    result = compare_snapshots([a, b])

    assert [entry.qualified_name for entry in result.entries] == [
        ("alpha", "Customer"),
        ("zeta", "Report"),
    ]


def test_identical_snapshots_produce_an_empty_diff() -> None:
    a = make_snapshot("a", ("sales", "Invoice"))
    b = make_snapshot("b", ("sales", "Invoice"))

    result = compare_snapshots([a, b])

    assert result.entries == ()
    assert result.compared_profiles == ("a", "b")


def test_column_missing_from_one_profile_of_matched_table() -> None:
    notes = make_column("notes")
    a = make_snapshot_with_tables(
        "a", make_table("sales", "Invoice", notes)
    )
    b = make_snapshot_with_tables("b", make_table("sales", "Invoice"))

    result = compare_snapshots([a, b])

    assert result.entries == (
        MissingColumn(
            schema_name="sales",
            table_name="Invoice",
            column_name="notes",
            missing_from_profile="b",
            present_attributes=(("a", ColumnAttributes.from_snapshot(notes)),),
        ),
    )


def test_column_missing_from_a_subset_of_matched_tables_profiles() -> None:
    notes_a = make_column("notes")
    notes_b = make_column("notes")
    a = make_snapshot_with_tables(
        "a", make_table("sales", "Invoice", notes_a)
    )
    b = make_snapshot_with_tables(
        "b", make_table("sales", "Invoice", notes_b)
    )
    c = make_snapshot_with_tables("c", make_table("sales", "Invoice"))
    d = make_snapshot_with_tables("d", make_table("sales", "Invoice"))

    result = compare_snapshots([a, b, c, d])

    present_attributes = (
        ("a", ColumnAttributes.from_snapshot(notes_a)),
        ("b", ColumnAttributes.from_snapshot(notes_b)),
    )
    assert result.entries == (
        MissingColumn(
            schema_name="sales",
            table_name="Invoice",
            column_name="notes",
            missing_from_profile="c",
            present_attributes=present_attributes,
        ),
        MissingColumn(
            schema_name="sales",
            table_name="Invoice",
            column_name="notes",
            missing_from_profile="d",
            present_attributes=present_attributes,
        ),
    )


def test_column_present_in_every_profile_produces_no_missing_column_entry() -> None:
    a = make_snapshot_with_tables(
        "a", make_table("sales", "Invoice", make_column("notes"))
    )
    b = make_snapshot_with_tables(
        "b", make_table("sales", "Invoice", make_column("notes"))
    )

    result = compare_snapshots([a, b])

    assert result.entries == ()


def test_table_missing_entirely_produces_no_missing_column_entries_for_that_profile() -> (
    None
):
    a = make_snapshot_with_tables(
        "a", make_table("sales", "Invoice", make_column("notes"))
    )
    b = make_snapshot_with_tables(
        "b", make_table("sales", "Invoice", make_column("notes"))
    )
    c = make_snapshot_with_tables("c")

    result = compare_snapshots([a, b, c])

    assert result.entries == (
        MissingTable(
            schema_name="sales", table_name="Invoice", missing_from_profile="c"
        ),
    )


def test_table_present_in_only_one_profile_produces_no_column_level_entries() -> None:
    a = make_snapshot_with_tables(
        "a", make_table("sales", "Invoice", make_column("notes"))
    )
    b = make_snapshot_with_tables("b")

    result = compare_snapshots([a, b])

    assert result.entries == (
        MissingTable(
            schema_name="sales", table_name="Invoice", missing_from_profile="b"
        ),
    )


def test_identical_column_attributes_produce_no_mismatch_entry() -> None:
    a = make_snapshot_with_tables(
        "a", make_table("sales", "Invoice", make_column("amount", data_type="decimal"))
    )
    b = make_snapshot_with_tables(
        "b", make_table("sales", "Invoice", make_column("amount", data_type="decimal"))
    )

    result = compare_snapshots([a, b])

    assert result.entries == ()


def test_differing_data_type_produces_one_mismatch_entry() -> None:
    attrs_a = make_column("amount", data_type="decimal")
    attrs_b = make_column("amount", data_type="float")
    a = make_snapshot_with_tables("a", make_table("sales", "Invoice", attrs_a))
    b = make_snapshot_with_tables("b", make_table("sales", "Invoice", attrs_b))

    result = compare_snapshots([a, b])

    assert result.entries == (
        ColumnMismatch(
            schema_name="sales",
            table_name="Invoice",
            column_name="amount",
            values_by_profile=(
                ("a", ColumnAttributes.from_snapshot(attrs_a)),
                ("b", ColumnAttributes.from_snapshot(attrs_b)),
            ),
        ),
    )


def test_type_variance_across_three_profiles_named_individually_in_one_entry() -> None:
    attrs_a = make_column("amount", data_type="decimal")
    attrs_b = make_column("amount", data_type="float")
    attrs_c = make_column("amount", data_type="money")
    a = make_snapshot_with_tables("a", make_table("sales", "Invoice", attrs_a))
    b = make_snapshot_with_tables("b", make_table("sales", "Invoice", attrs_b))
    c = make_snapshot_with_tables("c", make_table("sales", "Invoice", attrs_c))

    result = compare_snapshots([a, b, c])

    assert result.entries == (
        ColumnMismatch(
            schema_name="sales",
            table_name="Invoice",
            column_name="amount",
            values_by_profile=(
                ("a", ColumnAttributes.from_snapshot(attrs_a)),
                ("b", ColumnAttributes.from_snapshot(attrs_b)),
                ("c", ColumnAttributes.from_snapshot(attrs_c)),
            ),
        ),
    )


def test_nullable_only_difference_produces_a_mismatch_entry() -> None:
    attrs_a = make_column("notes", is_nullable=True)
    attrs_b = make_column("notes", is_nullable=False)
    a = make_snapshot_with_tables("a", make_table("sales", "Invoice", attrs_a))
    b = make_snapshot_with_tables("b", make_table("sales", "Invoice", attrs_b))

    result = compare_snapshots([a, b])

    assert result.entries == (
        ColumnMismatch(
            schema_name="sales",
            table_name="Invoice",
            column_name="notes",
            values_by_profile=(
                ("a", ColumnAttributes.from_snapshot(attrs_a)),
                ("b", ColumnAttributes.from_snapshot(attrs_b)),
            ),
        ),
    )


def test_ordinal_position_only_difference_produces_no_mismatch_entry() -> None:
    a = make_snapshot_with_tables(
        "a", make_table("sales", "Invoice", make_column("notes", ordinal_position=1))
    )
    b = make_snapshot_with_tables(
        "b", make_table("sales", "Invoice", make_column("notes", ordinal_position=2))
    )

    result = compare_snapshots([a, b])

    assert result.entries == ()


def test_none_vs_concrete_value_is_a_genuine_mismatch() -> None:
    attrs_a = make_column("code", character_maximum_length=None)
    attrs_b = make_column("code", character_maximum_length=50)
    a = make_snapshot_with_tables("a", make_table("sales", "Invoice", attrs_a))
    b = make_snapshot_with_tables("b", make_table("sales", "Invoice", attrs_b))

    result = compare_snapshots([a, b])

    assert result.entries == (
        ColumnMismatch(
            schema_name="sales",
            table_name="Invoice",
            column_name="code",
            values_by_profile=(
                ("a", ColumnAttributes.from_snapshot(attrs_a)),
                ("b", ColumnAttributes.from_snapshot(attrs_b)),
            ),
        ),
    )


def test_values_by_profile_is_ordered_by_profile_name() -> None:
    attrs_c = make_column("amount", data_type="money")
    attrs_a = make_column("amount", data_type="decimal")
    c = make_snapshot_with_tables("c", make_table("sales", "Invoice", attrs_c))
    a = make_snapshot_with_tables("a", make_table("sales", "Invoice", attrs_a))

    result = compare_snapshots([c, a])

    assert result.entries == (
        ColumnMismatch(
            schema_name="sales",
            table_name="Invoice",
            column_name="amount",
            values_by_profile=(
                ("a", ColumnAttributes.from_snapshot(attrs_a)),
                ("c", ColumnAttributes.from_snapshot(attrs_c)),
            ),
        ),
    )


def test_column_can_be_both_missing_and_mismatched_simultaneously() -> None:
    attrs_a = make_column("amount", data_type="decimal")
    attrs_b = make_column("amount", data_type="float")
    a = make_snapshot_with_tables("a", make_table("sales", "Invoice", attrs_a))
    b = make_snapshot_with_tables("b", make_table("sales", "Invoice", attrs_b))
    c = make_snapshot_with_tables("c", make_table("sales", "Invoice"))

    result = compare_snapshots([a, b, c])

    present_attributes = (
        ("a", ColumnAttributes.from_snapshot(attrs_a)),
        ("b", ColumnAttributes.from_snapshot(attrs_b)),
    )
    assert result.entries == (
        MissingColumn(
            schema_name="sales",
            table_name="Invoice",
            column_name="amount",
            missing_from_profile="c",
            present_attributes=present_attributes,
        ),
        ColumnMismatch(
            schema_name="sales",
            table_name="Invoice",
            column_name="amount",
            values_by_profile=present_attributes,
        ),
    )


def test_cross_type_ordering_missing_table_before_missing_column_before_mismatch() -> (
    None
):
    attrs_a = make_column("amount", data_type="decimal")
    attrs_b = make_column("amount", data_type="float")
    a = make_snapshot_with_tables(
        "a",
        make_table("sales", "Invoice", attrs_a),
        make_table("sales", "Payment", make_column("id")),
    )
    b = make_snapshot_with_tables("b", make_table("sales", "Invoice", attrs_b))

    result = compare_snapshots([a, b])

    assert result.entries == (
        ColumnMismatch(
            schema_name="sales",
            table_name="Invoice",
            column_name="amount",
            values_by_profile=(
                ("a", ColumnAttributes.from_snapshot(attrs_a)),
                ("b", ColumnAttributes.from_snapshot(attrs_b)),
            ),
        ),
        MissingTable(
            schema_name="sales", table_name="Payment", missing_from_profile="b"
        ),
    )


def test_same_type_entries_for_the_same_table_are_ordered_by_column_name() -> None:
    a = make_snapshot_with_tables(
        "a",
        make_table(
            "sales",
            "Invoice",
            make_column("zeta"),
            make_column("alpha"),
        ),
    )
    b = make_snapshot_with_tables("b", make_table("sales", "Invoice"))

    result = compare_snapshots([a, b])

    assert [entry.column_name for entry in result.entries] == ["alpha", "zeta"]


def test_column_level_entries_ordering_is_independent_of_input_snapshot_order() -> (
    None
):
    a = make_snapshot_with_tables(
        "a",
        make_table(
            "sales",
            "Invoice",
            make_column("zeta"),
            make_column("alpha"),
        ),
    )
    b = make_snapshot_with_tables("b", make_table("sales", "Invoice"))

    result_ab = compare_snapshots([a, b])
    result_ba = compare_snapshots([b, a])

    assert result_ab.entries == result_ba.entries
