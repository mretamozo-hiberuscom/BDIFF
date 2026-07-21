"""INFORMATION_SCHEMA catalog query text and row normalization for SQL Server."""

from schema_comparator.domain.schema.models import (
    ColumnSnapshot,
    SchemaSnapshot,
    TableSnapshot,
)

CATALOG_QUERY_SQL = """
SELECT
    c.TABLE_SCHEMA,
    c.TABLE_NAME,
    c.COLUMN_NAME,
    c.DATA_TYPE,
    c.CHARACTER_MAXIMUM_LENGTH,
    c.NUMERIC_PRECISION,
    c.NUMERIC_SCALE,
    c.IS_NULLABLE,
    c.ORDINAL_POSITION
FROM INFORMATION_SCHEMA.COLUMNS c
INNER JOIN INFORMATION_SCHEMA.TABLES t
    ON t.TABLE_SCHEMA = c.TABLE_SCHEMA
   AND t.TABLE_NAME = c.TABLE_NAME
WHERE t.TABLE_TYPE = 'BASE TABLE'
""".strip()


def build_snapshot(profile_name: str, rows: list[tuple]) -> SchemaSnapshot:
    """Group and sort raw catalog rows into a deterministic `SchemaSnapshot`."""
    grouped: dict[tuple[str, str], list[ColumnSnapshot]] = {}
    for (
        schema,
        table,
        col_name,
        data_type,
        char_len,
        num_prec,
        num_scale,
        is_nullable,
        ordinal,
    ) in rows:
        grouped.setdefault((schema, table), []).append(
            ColumnSnapshot(
                name=col_name,
                data_type=data_type,
                character_maximum_length=char_len,
                numeric_precision=num_prec,
                numeric_scale=num_scale,
                is_nullable=(is_nullable == "YES"),
                ordinal_position=ordinal,
            )
        )

    tables = tuple(
        TableSnapshot(
            schema_name=schema,
            table_name=table,
            columns=tuple(sorted(cols, key=lambda c: (c.ordinal_position, c.name))),
        )
        for (schema, table), cols in sorted(grouped.items())
    )
    return SchemaSnapshot(profile_name=profile_name, tables=tables)


# Alias for backward compatibility
_build_snapshot = build_snapshot
