"""Unit tests for canonical domain models and capabilities."""

from schema_comparator.domain import (
    ComparisonMode,
    ProviderCapabilities,
    QualifiedName,
    SqlType,
    TypeFamily,
)
from schema_comparator.domain.comparison.models import ColumnAttributes
from schema_comparator.domain.schema.models import ColumnSnapshot


def test_qualified_name_formatting() -> None:
    qn1 = QualifiedName(object_name="users")
    assert qn1.format_qualified() == "users"

    qn2 = QualifiedName(object_name="users", schema_name="dbo")
    assert qn2.format_qualified() == "dbo.users"

    qn3 = QualifiedName(object_name="users", schema_name="dbo", catalog_name="AppDB")
    assert qn3.format_qualified() == "AppDB.dbo.users"


def test_sql_type_and_family() -> None:
    t = SqlType(native_type="VARCHAR2", family=TypeFamily.STRING)
    assert t.native_type == "VARCHAR2"
    assert t.family == TypeFamily.STRING


def test_provider_capabilities() -> None:
    caps = ProviderCapabilities(provider_id="postgresql", supports_schemas=True)
    assert caps.provider_id == "postgresql"
    assert caps.supports_schemas is True
    assert ComparisonMode.NATIVE_STRICT == "native-strict"


def test_column_snapshot_extended_attributes() -> None:
    col = ColumnSnapshot(
        name="id",
        data_type="int",
        character_maximum_length=None,
        numeric_precision=10,
        numeric_scale=0,
        is_nullable=False,
        ordinal_position=1,
        default_expression="0",
        is_identity=True,
        collation="Latin1_General_CI_AS",
    )
    assert col.default_expression == "0"
    assert col.is_identity is True
    assert col.collation == "Latin1_General_CI_AS"

    attrs = ColumnAttributes.from_snapshot(col)
    assert attrs.default_expression == "0"
    assert attrs.is_identity is True
    assert attrs.collation == "Latin1_General_CI_AS"
