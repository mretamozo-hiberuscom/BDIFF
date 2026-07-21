"""SQLite schema introspector using PRAGMA commands and sqlite_master."""

import sqlite3

from schema_comparator.domain.schema.models import (
    ColumnSnapshot,
    SchemaSnapshot,
    TableSnapshot,
)

SQLITE_TABLE_LIST_SQL = """
SELECT name FROM sqlite_master 
WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
ORDER BY name;
""".strip()


def _parse_sqlite_data_type(type_str: str) -> tuple[str, int | None, int | None, int | None]:
    """Parse SQLite native data type string into clean_type, char_len, precision, scale."""
    if not type_str:
        return ("TEXT", None, None, None)

    upper_type = type_str.strip().upper()
    if "(" in upper_type and ")" in upper_type:
        clean_type = upper_type.split("(")[0].strip()
        params_str = upper_type.split("(")[1].split(")")[0].strip()
        params = [p.strip() for p in params_str.split(",") if p.strip().isdigit()]
        
        if clean_type in ("DECIMAL", "NUMERIC", "NUMBER"):
            if len(params) == 1:
                return (clean_type, None, int(params[0]), None)
            elif len(params) >= 2:
                return (clean_type, None, int(params[0]), int(params[1]))
        else:
            if len(params) == 1:
                return (clean_type, int(params[0]), None, None)
            elif len(params) >= 2:
                return (clean_type, None, int(params[0]), int(params[1]))

        return (clean_type, None, None, None)

    return (upper_type, None, None, None)


def introspect_sqlite_schema(conn: sqlite3.Connection, profile_name: str) -> SchemaSnapshot:
    """Extract SchemaSnapshot from an open SQLite connection."""
    cursor = conn.cursor()
    try:
        cursor.execute(SQLITE_TABLE_LIST_SQL)
        table_rows = cursor.fetchall()
        tables: list[TableSnapshot] = []

        for (table_name,) in table_rows:
            escaped_name = table_name.replace('"', '""')
            try:
                cursor.execute(f'PRAGMA table_xinfo("{escaped_name}")')
                xinfo_rows = cursor.fetchall()
            except sqlite3.Error:
                cursor.execute(f'PRAGMA table_info("{escaped_name}")')
                xinfo_rows = cursor.fetchall()

            # Count total primary key columns in this table
            pk_count = sum(1 for row in xinfo_rows if row[5] > 0)

            columns: list[ColumnSnapshot] = []
            for col_row in xinfo_rows:
                cid = col_row[0]
                col_name = col_row[1]
                raw_type = col_row[2] or "TEXT"
                notnull = col_row[3]
                dflt_value = col_row[4]
                pk = col_row[5]

                clean_type, char_len, num_prec, num_scale = _parse_sqlite_data_type(raw_type)
                # In SQLite, only single-column INTEGER PRIMARY KEY acts as autoincrement ROWID identity
                is_identity = (pk == 1 and pk_count == 1 and clean_type in ("INTEGER", "INT"))

                columns.append(
                    ColumnSnapshot(
                        name=col_name,
                        data_type=clean_type,
                        character_maximum_length=char_len,
                        numeric_precision=num_prec,
                        numeric_scale=num_scale,
                        is_nullable=(notnull == 0),
                        ordinal_position=cid + 1,
                        default_expression=str(dflt_value) if dflt_value is not None else None,
                        is_identity=is_identity,
                    )
                )

            tables.append(
                TableSnapshot(
                    schema_name="main",
                    table_name=table_name,
                    columns=tuple(sorted(columns, key=lambda c: (c.ordinal_position, c.name))),
                )
            )

        return SchemaSnapshot(
            profile_name=profile_name,
            tables=tuple(sorted(tables, key=lambda t: (t.schema_name, t.table_name))),
        )
    finally:
        cursor.close()
