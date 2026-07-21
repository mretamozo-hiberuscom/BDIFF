"""PostgreSQL catalog query and row normalization."""

from schema_comparator.domain.schema.models import (
    ColumnSnapshot,
    SchemaSnapshot,
    TableSnapshot,
)

POSTGRESQL_CATALOG_QUERY_SQL = """
SELECT
    c.table_schema,
    c.table_name,
    c.column_name,
    c.data_type,
    c.character_maximum_length,
    c.numeric_precision,
    c.numeric_scale,
    c.is_nullable,
    c.ordinal_position,
    c.column_default,
    c.is_identity,
    c.collation_name
FROM information_schema.columns c
INNER JOIN information_schema.tables t
    ON t.table_schema = c.table_schema
   AND t.table_name = c.table_name
WHERE t.table_type = 'BASE TABLE'
  AND c.table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY c.table_schema, c.table_name, c.ordinal_position;
""".strip()


def build_snapshot(profile_name: str, rows: list[tuple]) -> SchemaSnapshot:
    """Group raw PostgreSQL catalog rows into a deterministic SchemaSnapshot."""
    grouped: dict[tuple[str, str], list[ColumnSnapshot]] = {}
    for row in rows:
        (
            schema,
            table,
            col_name,
            data_type,
            char_len,
            num_prec,
            num_scale,
            is_nullable,
            ordinal,
            col_default,
            is_identity,
            collation,
        ) = row[:12]

        is_identity_bool = (is_identity == "YES") or (
            col_default is not None and "nextval(" in str(col_default).lower()
        )

        grouped.setdefault((schema, table), []).append(
            ColumnSnapshot(
                name=col_name,
                data_type=data_type,
                character_maximum_length=char_len,
                numeric_precision=num_prec,
                numeric_scale=num_scale,
                is_nullable=(is_nullable == "YES"),
                ordinal_position=ordinal,
                default_expression=col_default,
                is_identity=is_identity_bool,
                collation=collation,
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
