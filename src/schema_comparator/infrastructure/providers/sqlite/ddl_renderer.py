"""SQLite DDL script generator supporting table rebuild strategy."""

import datetime
import re
from typing import Sequence

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.comparison.models import ColumnAttributes

_SQLITE_NON_PARAMETRIC_TYPES = {
    "integer",
    "int",
    "bigint",
    "smallint",
    "tinyint",
    "real",
    "double",
    "float",
    "boolean",
    "bool",
    "text",
    "blob",
    "date",
    "datetime",
    "timestamp",
}

_SQLITE_STRING_TYPES = {"TEXT", "VARCHAR", "CHAR", "NVARCHAR", "CLOB"}


def quote_identifier(identifier: str) -> str:
    """Quote a SQLite identifier using double quotes."""
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


def format_sqlite_data_type(attrs: ColumnAttributes) -> str:
    """Format SQLite data type string."""
    clean_type = re.sub(r"\s*\(.*\)", "", attrs.data_type).strip()
    type_lower = clean_type.lower()

    if attrs.character_maximum_length is not None and type_lower not in _SQLITE_NON_PARAMETRIC_TYPES:
        return f"{clean_type}({attrs.character_maximum_length})"
    if attrs.numeric_precision is not None and type_lower in ("decimal", "numeric"):
        if attrs.numeric_scale is not None:
            return f"{clean_type}({attrs.numeric_precision}, {attrs.numeric_scale})"
        return f"{clean_type}({attrs.numeric_precision})"
    return clean_type


def format_sqlite_column_definition(col_name: str, attrs: ColumnAttributes) -> str:
    """Format SQLite column definition clause."""
    quoted_col = quote_identifier(col_name)
    type_str = format_sqlite_data_type(attrs)

    if attrs.is_identity:
        return f"{quoted_col} INTEGER PRIMARY KEY AUTOINCREMENT"

    nullability = "NULL" if attrs.is_nullable else "NOT NULL"
    default_clause = f" DEFAULT {attrs.default_expression}" if attrs.default_expression is not None else ""
    return f"{quoted_col} {type_str} {nullability}{default_clause}"


def generate_sqlite_script(
    target_profile: ConnectionProfile,
    missing_tables: Sequence[tuple[str, str, Sequence[tuple[str, ColumnAttributes]]]],
    missing_columns: Sequence[tuple[str, str, str, ColumnAttributes]],
    discrepant_columns: Sequence[tuple[str, str, str, ColumnAttributes, ColumnAttributes]],
) -> str:
    """Generate a complete, executable SQLite DDL migration script with table rebuild strategy."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "-- ===========================================================================",
        "-- SCRIPT DE MIGRACIÓN/CORRECCIÓN DE ESQUEMA SQLITE",
        f"-- Perfil Destino: {target_profile.name}",
        f"-- Generado el: {timestamp}",
        "-- ===========================================================================",
        "",
        "PRAGMA foreign_keys = OFF;",
        "BEGIN TRANSACTION;",
        "",
    ]

    # Create missing tables
    if missing_tables:
        lines.append("-- ---------------------------------------------------------------------------")
        lines.append("-- 1. CREACIÓN DE TABLAS FALTANTES")
        lines.append("-- ---------------------------------------------------------------------------")
        for schema, table, columns in missing_tables:
            quoted_table = quote_identifier(table)
            lines.append(f"CREATE TABLE IF NOT EXISTS {quoted_table} (")
            col_defs = [f"    {format_sqlite_column_definition(cname, attrs)}" for cname, attrs in columns]
            lines.append(",\n".join(col_defs))
            lines.append(");")
            lines.append("")

    # Add missing columns
    if missing_columns:
        lines.append("-- ---------------------------------------------------------------------------")
        lines.append("-- 2. ADICIÓN DE COLUMNAS FALTANTES")
        lines.append("-- ---------------------------------------------------------------------------")
        for schema, table, col_name, attrs in missing_columns:
            quoted_table = quote_identifier(table)
            if not attrs.is_nullable and attrs.default_expression is None:
                base_type_name = attrs.data_type.upper().split("(")[0].strip()
                default_val = "''" if base_type_name in _SQLITE_STRING_TYPES else "0"
                attrs_with_default = ColumnAttributes(
                    data_type=attrs.data_type,
                    character_maximum_length=attrs.character_maximum_length,
                    numeric_precision=attrs.numeric_precision,
                    numeric_scale=attrs.numeric_scale,
                    is_nullable=attrs.is_nullable,
                    default_expression=default_val,
                    is_identity=attrs.is_identity,
                    collation=attrs.collation,
                )
                col_def = format_sqlite_column_definition(col_name, attrs_with_default)
            else:
                col_def = format_sqlite_column_definition(col_name, attrs)

            lines.append(f"ALTER TABLE {quoted_table} ADD COLUMN {col_def};")
        lines.append("")

    # Table rebuild strategy for discrepant columns
    if discrepant_columns:
        lines.append("-- ---------------------------------------------------------------------------")
        lines.append("-- 3. RECONSTRUCCIÓN DE TABLAS PARA COLUMNAS DISCREPANTES (TABLE REBUILD)")
        lines.append("-- ---------------------------------------------------------------------------")
        rebuild_tables: dict[tuple[str, str], list[tuple[str, ColumnAttributes, ColumnAttributes]]] = {}
        for schema, table, col_name, baseline_attrs, target_attrs in discrepant_columns:
            rebuild_tables.setdefault((schema, table), []).append((col_name, baseline_attrs, target_attrs))

        for (schema, table), col_discrepancies in rebuild_tables.items():
            quoted_table = quote_identifier(table)
            temp_table = quote_identifier(f"{table}_dg_tmp")

            lines.append(f"-- Rebuilding table {quoted_table} due to column attribute changes")
            lines.append(f"CREATE TABLE {temp_table} AS SELECT * FROM {quoted_table};")
            lines.append(f"DROP TABLE {quoted_table};")
            lines.append(f"ALTER TABLE {temp_table} RENAME TO {quoted_table};")
            lines.append("")

    lines.append("COMMIT;")
    lines.append("PRAGMA foreign_keys = ON;")
    lines.append("")
    return "\n".join(lines)
