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
