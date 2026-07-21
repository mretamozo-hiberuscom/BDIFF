"""Unit tests for schema_comparator.report.attributes: format_attributes."""

from schema_comparator.compare.models import ColumnAttributes
from schema_comparator.report.attributes import format_attributes


def test_format_attributes_integer_with_numeric_precision() -> None:
    attrs = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=10,
        numeric_scale=0,
        is_nullable=False,
    )
    assert format_attributes(attrs) == "int, NOT NULL"


def test_format_attributes_integer_with_embedded_precision() -> None:
    attrs = ColumnAttributes(
        data_type="INT(10, 0)",
        character_maximum_length=None,
        numeric_precision=10,
        numeric_scale=0,
        is_nullable=True,
    )
    assert format_attributes(attrs) == "INT, NULL"


def test_format_attributes_decimal_with_precision_and_scale() -> None:
    attrs = ColumnAttributes(
        data_type="decimal",
        character_maximum_length=None,
        numeric_precision=18,
        numeric_scale=4,
        is_nullable=False,
    )
    assert format_attributes(attrs) == "decimal(18,4), NOT NULL"


def test_format_attributes_varchar_with_length() -> None:
    attrs = ColumnAttributes(
        data_type="varchar",
        character_maximum_length=100,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=True,
    )
    assert format_attributes(attrs) == "varchar(100), NULL"
