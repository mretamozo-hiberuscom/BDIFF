"""MySQL & MariaDB catalog query and row normalization."""

from schema_comparator.domain.schema.models import (
    ColumnSnapshot,
    SchemaFeature,
    SchemaSnapshot,
    TableSnapshot,
)

MYSQL_FAMILY_CATALOG_QUERY_SQL = """
SELECT
    c.TABLE_SCHEMA,
    c.TABLE_NAME,
    c.COLUMN_NAME,
    c.DATA_TYPE,
    c.CHARACTER_MAXIMUM_LENGTH,
    c.NUMERIC_PRECISION,
    c.NUMERIC_SCALE,
    c.IS_NULLABLE,
    c.ORDINAL_POSITION,
    c.COLUMN_DEFAULT,
    c.EXTRA,
    c.COLLATION_NAME
FROM information_schema.COLUMNS c
INNER JOIN information_schema.TABLES t
    ON t.TABLE_SCHEMA = c.TABLE_SCHEMA
   AND t.TABLE_NAME = c.TABLE_NAME
WHERE t.TABLE_TYPE = 'BASE TABLE'
  AND c.TABLE_SCHEMA NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
  AND (c.TABLE_SCHEMA = DATABASE() OR DATABASE() IS NULL OR DATABASE() = '')
ORDER BY c.TABLE_SCHEMA, c.TABLE_NAME, c.ORDINAL_POSITION;
""".strip()


def build_snapshot(
    profile_name: str, rows: list[tuple], provider_id: str = "mysql"
) -> SchemaSnapshot:
    """Group raw MySQL/MariaDB catalog rows into a deterministic SchemaSnapshot."""
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
            extra,
            collation,
        ) = row[:12]

        is_identity_bool = bool(extra and "auto_increment" in str(extra).lower())

        grouped.setdefault((schema, table), []).append(
            ColumnSnapshot(
                name=col_name,
                data_type=data_type,
                character_maximum_length=char_len,
                numeric_precision=num_prec,
                numeric_scale=num_scale,
                is_nullable=(is_nullable == "YES"),
                ordinal_position=ordinal,
                default_expression=str(col_default) if col_default is not None else None,
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
    return SchemaSnapshot(
        profile_name=profile_name,
        provider_id=provider_id,
        tables=tables,
        extracted_features=frozenset({SchemaFeature.TABLES}),
    )
