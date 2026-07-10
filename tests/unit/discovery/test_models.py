"""Unit tests for discovery.models: qualified identity and immutability."""

import dataclasses

import pytest

from schema_comparator.discovery.models import ColumnSnapshot, TableSnapshot


def _column(name="id", ordinal=1) -> ColumnSnapshot:
    return ColumnSnapshot(
        name=name,
        data_type="int",
        character_maximum_length=None,
        numeric_precision=10,
        numeric_scale=0,
        is_nullable=False,
        ordinal_position=ordinal,
    )


def test_qualified_name_returns_schema_and_table_pair() -> None:
    table = TableSnapshot(schema_name="sales", table_name="Invoice", columns=(_column(),))
    assert table.qualified_name == ("sales", "Invoice")


def test_same_named_tables_in_different_schemas_are_distinct() -> None:
    sales_invoice = TableSnapshot(schema_name="sales", table_name="Invoice", columns=(_column(),))
    archive_invoice = TableSnapshot(schema_name="archive", table_name="Invoice", columns=(_column(),))

    assert sales_invoice.qualified_name != archive_invoice.qualified_name
    assert sales_invoice != archive_invoice


def test_table_snapshot_is_immutable() -> None:
    table = TableSnapshot(schema_name="sales", table_name="Invoice", columns=(_column(),))
    with pytest.raises(dataclasses.FrozenInstanceError):
        table.table_name = "Changed"  # type: ignore[misc]


def test_column_snapshot_is_immutable() -> None:
    column = _column()
    with pytest.raises(dataclasses.FrozenInstanceError):
        column.name = "changed"  # type: ignore[misc]


def test_column_snapshot_preserves_null_size_precision_scale() -> None:
    column = ColumnSnapshot(
        name="notes",
        data_type="text",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=True,
        ordinal_position=2,
    )
    assert column.character_maximum_length is None
    assert column.numeric_precision is None
    assert column.numeric_scale is None
