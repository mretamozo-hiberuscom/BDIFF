"""Resolutions built from the consolidation decisions."""

from schema_comparator.compare.models import ColumnAttributes, ColumnMismatch
from schema_comparator.tui.decision_model import build_resolutions


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
