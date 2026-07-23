"""Shared fixture helper for comparison-engine unit tests."""

from schema_comparator.discovery.models import ColumnSnapshot, SchemaSnapshot, TableSnapshot


def make_snapshot(profile_name: str, *tables: tuple[str, str]) -> SchemaSnapshot:
    """Build a SchemaSnapshot with empty-column tables for the given
    (schema_name, table_name) pairs — sufficient for comparison-engine
    tests, which never inspect column data."""
    return SchemaSnapshot(
        profile_name=profile_name,
        provider_id="sqlserver",
        tables=tuple(
            TableSnapshot(schema_name=s, table_name=t, columns=())
            for s, t in sorted(tables)
        ),
    )


def make_column(
    name: str,
    *,
    data_type: str = "int",
    character_maximum_length: int | None = None,
    numeric_precision: int | None = None,
    numeric_scale: int | None = None,
    is_nullable: bool = False,
    ordinal_position: int = 1,
) -> ColumnSnapshot:
    """Build a ColumnSnapshot with sensible defaults so each test only
    overrides the field(s) it is actually exercising."""
    return ColumnSnapshot(
        name=name,
        data_type=data_type,
        character_maximum_length=character_maximum_length,
        numeric_precision=numeric_precision,
        numeric_scale=numeric_scale,
        is_nullable=is_nullable,
        ordinal_position=ordinal_position,
    )


def make_table(
    schema_name: str, table_name: str, *columns: ColumnSnapshot
) -> TableSnapshot:
    """Build a TableSnapshot for the given schema/table with the given
    columns."""
    return TableSnapshot(
        schema_name=schema_name, table_name=table_name, columns=tuple(columns)
    )


def make_snapshot_with_tables(
    profile_name: str, *tables: TableSnapshot
) -> SchemaSnapshot:
    """Build a SchemaSnapshot from already-constructed TableSnapshots —
    used by column-level fixtures that need real column data."""
    return SchemaSnapshot(profile_name=profile_name, provider_id="sqlserver", tables=tuple(tables))
