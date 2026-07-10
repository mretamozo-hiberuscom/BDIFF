"""Unit tests for compare.engine: union, missing-table detection, ordering."""

from schema_comparator.compare.engine import compare_snapshots
from schema_comparator.compare.models import MissingTable
from compare.conftest import make_snapshot


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
