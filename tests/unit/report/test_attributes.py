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


def test_format_attributes_shows_every_attribute_that_can_differ() -> None:
    from schema_comparator.compare.models import ColumnAttributes
    from schema_comparator.report.attributes import format_attributes

    attrs = ColumnAttributes(
        data_type="datetime2",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
        default_expression="(getdate())",
        datetime_precision=3,
    )
    text = ColumnAttributes(
        data_type="varchar",
        character_maximum_length=10,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=True,
        is_identity=False,
        collation="Latin1_General_CS_AS",
    )
    ident = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=10,
        numeric_scale=0,
        is_nullable=False,
        is_identity=True,
    )

    assert format_attributes(attrs) == "datetime2(3), NOT NULL, DEFAULT (getdate())"
    assert format_attributes(text) == "varchar(10), NULL, COLLATE Latin1_General_CS_AS"
    assert format_attributes(ident) == "int, NOT NULL, IDENTITY"
