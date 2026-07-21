"""Oracle catalog query and row normalization."""

from schema_comparator.domain.schema.models import (
    ColumnSnapshot,
    SchemaSnapshot,
    TableSnapshot,
)

ORACLE_CATALOG_QUERY_SQL = """
SELECT
    c.OWNER,
    c.TABLE_NAME,
    c.COLUMN_NAME,
    c.DATA_TYPE,
    c.CHAR_LENGTH,
    c.DATA_PRECISION,
    c.DATA_SCALE,
    c.NULLABLE,
    c.COLUMN_ID,
    c.DATA_DEFAULT,
    c.IDENTITY_COLUMN
FROM ALL_TAB_COLS c
INNER JOIN ALL_TABLES t
    ON t.OWNER = c.OWNER
   AND t.TABLE_NAME = c.TABLE_NAME
WHERE c.OWNER NOT IN (
    'SYS', 'SYSTEM', 'OUTLN', 'DBSNMP', 'ORACLE_OCM', 'AUDSYS', 'CTXSYS',
    'MDSYS', 'XDB', 'WMSYS', 'LBACSYS', 'GSMADMIN_INTERNAL', 'ORDS_METADATA',
    'OLAPSYS', 'EXFSYS', 'FLOWS_FILES', 'APEX_040200', 'APEX_050000', 'APEX_180100'
)
  AND c.USER_GENERATED = 'YES'
ORDER BY c.OWNER, c.TABLE_NAME, c.COLUMN_ID;
""".strip()


def build_snapshot(profile_name: str, rows: list[tuple]) -> SchemaSnapshot:
    """Group raw Oracle catalog rows into a deterministic SchemaSnapshot."""
    grouped: dict[tuple[str, str], list[ColumnSnapshot]] = {}
    for row in rows:
        (
            owner,
            table,
            col_name,
            data_type,
            char_len,
            num_prec,
            num_scale,
            nullable,
            column_id,
            data_default,
            identity_col,
        ) = row[:11]

        is_identity_bool = (identity_col == "YES")

        grouped.setdefault((owner, table), []).append(
            ColumnSnapshot(
                name=col_name,
                data_type=data_type,
                character_maximum_length=char_len,
                numeric_precision=num_prec,
                numeric_scale=num_scale,
                is_nullable=(nullable == "Y"),
                ordinal_position=column_id,
                default_expression=str(data_default).strip() if data_default is not None else None,
                is_identity=is_identity_bool,
                collation=None,
            )
        )

    tables = tuple(
        TableSnapshot(
            schema_name=owner,
            table_name=table,
            columns=tuple(sorted(cols, key=lambda c: (c.ordinal_position or 0, c.name))),
        )
        for (owner, table), cols in sorted(grouped.items())
    )
    return SchemaSnapshot(profile_name=profile_name, tables=tables)
