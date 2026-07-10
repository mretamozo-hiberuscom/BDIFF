"""Unit tests for compare.models: qualified identity and immutability."""

import dataclasses

import pytest

from schema_comparator.compare.models import (
    ColumnAttributes,
    ColumnMismatch,
    ComparisonResult,
    MissingColumn,
    MissingTable,
)
from schema_comparator.discovery.models import ColumnSnapshot


def test_qualified_name_returns_schema_and_table_pair() -> None:
    entry = MissingTable(
        schema_name="sales", table_name="Invoice", missing_from_profile="staging"
    )
    assert entry.qualified_name == ("sales", "Invoice")


def test_missing_table_is_immutable() -> None:
    entry = MissingTable(
        schema_name="sales", table_name="Invoice", missing_from_profile="staging"
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.table_name = "Changed"  # type: ignore[misc]


def test_comparison_result_is_immutable() -> None:
    result = ComparisonResult(compared_profiles=("a", "b"), entries=())
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.entries = ()  # type: ignore[misc]


def test_column_attributes_from_snapshot_copies_comparable_fields() -> None:
    column = ColumnSnapshot(
        name="amount",
        data_type="decimal",
        character_maximum_length=None,
        numeric_precision=18,
        numeric_scale=2,
        is_nullable=False,
        ordinal_position=3,
    )

    attributes = ColumnAttributes.from_snapshot(column)

    assert attributes == ColumnAttributes(
        data_type="decimal",
        character_maximum_length=None,
        numeric_precision=18,
        numeric_scale=2,
        is_nullable=False,
    )


def test_column_attributes_excludes_ordinal_position_and_name() -> None:
    field_names = {f.name for f in dataclasses.fields(ColumnAttributes)}
    assert "ordinal_position" not in field_names
    assert "name" not in field_names


def test_column_attributes_equal_instances_compare_equal() -> None:
    a = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )
    b = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )

    assert a == b


def test_column_attributes_differing_instances_compare_unequal() -> None:
    a = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )
    b = ColumnAttributes(
        data_type="varchar",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )

    assert a != b


def test_missing_column_qualified_name_returns_schema_and_table_pair() -> None:
    entry = MissingColumn(
        schema_name="sales",
        table_name="Invoice",
        column_name="notes",
        missing_from_profile="staging",
    )
    assert entry.qualified_name == ("sales", "Invoice")


def test_missing_column_is_immutable() -> None:
    entry = MissingColumn(
        schema_name="sales",
        table_name="Invoice",
        column_name="notes",
        missing_from_profile="staging",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.column_name = "Changed"  # type: ignore[misc]


def test_column_mismatch_qualified_name_returns_schema_and_table_pair() -> None:
    attrs = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )
    entry = ColumnMismatch(
        schema_name="sales",
        table_name="Invoice",
        column_name="amount",
        values_by_profile=(("a", attrs), ("b", attrs)),
    )
    assert entry.qualified_name == ("sales", "Invoice")


def test_column_mismatch_is_immutable() -> None:
    attrs = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )
    entry = ColumnMismatch(
        schema_name="sales",
        table_name="Invoice",
        column_name="amount",
        values_by_profile=(("a", attrs), ("b", attrs)),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.column_name = "Changed"  # type: ignore[misc]
