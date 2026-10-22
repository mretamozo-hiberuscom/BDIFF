"""Resolutions built from the consolidation decisions."""

from schema_comparator.compare.models import ColumnAttributes, ColumnMismatch
from schema_comparator.tui.decision_model import ColumnOptions, build_resolutions


def _attrs(length: int) -> ColumnAttributes:
    return ColumnAttributes(
        data_type="varchar",
        character_maximum_length=length,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=True,
    )


def test_a_mismatch_fix_carries_what_each_destination_had() -> None:
    mismatch = ColumnMismatch(
        schema_name="dbo",
        table_name="t",
        column_name="c",
        values_by_profile=(("a", _attrs(40)), ("b", _attrs(10)), ("c", _attrs(20))),
    )

    resolutions = build_resolutions({mismatch: (_attrs(40), ("b", "c"))})

    (resolution,) = resolutions.columns
    assert resolution.observed_by_profile == (("b", _attrs(10)), ("c", _attrs(20)))


def test_a_column_fix_carries_the_fill_value_and_accepted_loss() -> None:
    mismatch = ColumnMismatch(
        schema_name="dbo",
        table_name="t",
        column_name="c",
        values_by_profile=(("a", _attrs(40)), ("b", _attrs(10))),
    )

    resolutions = build_resolutions(
        {mismatch: (_attrs(10), ("a",))},
        {mismatch: ColumnOptions(backfill_value="N/D", accept_data_loss=True)},
    )

    (resolution,) = resolutions.columns
    assert resolution.backfill_value == "N/D"
    assert resolution.accept_data_loss is True


def test_a_blank_fill_value_means_none() -> None:
    mismatch = ColumnMismatch(
        schema_name="dbo",
        table_name="t",
        column_name="c",
        values_by_profile=(("a", _attrs(40)), ("b", _attrs(10))),
    )

    resolutions = build_resolutions(
        {mismatch: (_attrs(10), ("a",))},
        {mismatch: ColumnOptions(backfill_value="   ")},
    )

    assert resolutions.columns[0].backfill_value is None


def test_drops_carry_what_each_destination_had() -> None:
    from schema_comparator.compare.consolidation import ColumnAction, TableAction
    from schema_comparator.compare.models import NamedColumnAttributes
    from schema_comparator.tui.decision_model import (
        MergedMissingColumn,
        MergedMissingTable,
    )

    table = MergedMissingTable(
        schema_name="dbo",
        table_name="t",
        missing_from_profiles=("c",),
        present_columns=(
            ("a", (NamedColumnAttributes("x", _attrs(1)),)),
            ("b", (NamedColumnAttributes("x", _attrs(2)),)),
        ),
    )
    column = MergedMissingColumn(
        schema_name="dbo",
        table_name="t",
        column_name="x",
        missing_from_profiles=("c",),
        present_attributes=(("a", _attrs(1)), ("b", _attrs(2))),
    )

    resolutions = build_resolutions(
        {table: (TableAction.DROP, ("b",)), column: (ColumnAction.DROP, ("a",))}
    )

    assert resolutions.table_deletions[0].observed_columns_by_profile == (
        ("b", (NamedColumnAttributes("x", _attrs(2)),)),
    )
    assert resolutions.column_deletions[0].observed_by_profile == (("a", _attrs(1)),)


def _mismatch() -> ColumnMismatch:
    return ColumnMismatch(
        schema_name="dbo",
        table_name="t",
        column_name="c",
        values_by_profile=(("a", _attrs(40)), ("b", _attrs(10)), ("c", _attrs(40))),
    )


def test_a_mismatch_fix_is_offered_only_where_the_column_differs() -> None:
    from schema_comparator.tui.decision_model import destination_choices

    # "a" and "c" already have the chosen definition; "d" has no such column.
    assert destination_choices(_mismatch(), _attrs(40)) == ("b",)
    assert destination_choices(_mismatch(), _attrs(10)) == ("a", "c")


def test_a_mismatch_drop_is_offered_where_the_column_exists() -> None:
    from schema_comparator.compare.consolidation import ColumnAction
    from schema_comparator.tui.decision_model import destination_choices

    assert destination_choices(_mismatch(), ColumnAction.DROP) == ("a", "b", "c")


def test_a_mismatch_fix_ignores_destinations_that_do_not_differ() -> None:
    resolutions = build_resolutions({_mismatch(): (_attrs(40), ("a", "b", "z"))})

    (resolution,) = resolutions.columns
    assert resolution.profiles_to_update == ("b",)
    assert resolution.observed_by_profile == (("b", _attrs(10)),)


def test_a_mismatch_fix_with_no_valid_destination_builds_nothing() -> None:
    assert build_resolutions({_mismatch(): (_attrs(40), ("a", "c"))}).is_empty()


def test_the_drops_to_confirm_name_each_object_and_its_profiles() -> None:
    from schema_comparator.compare.consolidation import ColumnAction, TableAction
    from schema_comparator.compare.models import NamedColumnAttributes
    from schema_comparator.tui.decision_model import (
        DropItem,
        MergedMissingColumn,
        MergedMissingTable,
        drops_in,
    )

    table = MergedMissingTable(
        schema_name="dbo",
        table_name="logs",
        missing_from_profiles=("c",),
        present_columns=(("a", (NamedColumnAttributes("x", _attrs(1)),)),),
    )
    column = MergedMissingColumn(
        schema_name="dbo",
        table_name="users",
        column_name="age",
        missing_from_profiles=("c",),
        present_attributes=(("a", _attrs(1)), ("b", _attrs(2))),
    )
    resolutions = build_resolutions(
        {
            table: (TableAction.DROP, ("a",)),
            column: (ColumnAction.DROP, ("a", "b")),
            _mismatch(): (_attrs(40), ("b",)),
        }
    )

    assert drops_in(resolutions) == (
        DropItem(kind="tabla", name="dbo.logs", profiles=("a",)),
        DropItem(kind="columna", name="dbo.users.age", profiles=("a", "b")),
    )


def test_a_resolution_without_drops_asks_for_no_confirmation() -> None:
    from schema_comparator.tui.decision_model import drops_in

    assert drops_in(build_resolutions({_mismatch(): (_attrs(40), ("b",))})) == ()
