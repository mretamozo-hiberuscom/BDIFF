"""PostgreSQL DDL script generator."""

import datetime
import re
from typing import Sequence

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.comparison.models import ColumnAttributes

_PG_NON_PARAMETRIC_TYPES = {
    "boolean",
    "bool",
    "integer",
    "int",
    "int4",
    "bigint",
    "int8",
    "smallint",
    "int2",
    "serial",
    "serial4",
    "bigserial",
    "serial8",
    "smallserial",
    "text",
    "date",
    "time",
    "timetz",
    "timestamp",
    "timestamptz",
    "timestamp with time zone",
    "timestamp without time zone",
    "interval",
    "uuid",
    "json",
    "jsonb",
    "bytea",
    "double precision",
    "float8",
    "real",
    "float4",
}


def quote_identifier(identifier: str) -> str:
    """Quote a PostgreSQL identifier using double quotes."""
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


def format_pg_data_type(attrs: ColumnAttributes) -> str:
    """Format PostgreSQL data type string including length, precision, and scale."""
    clean_type = re.sub(r"\s*\(.*\)", "", attrs.data_type).strip()
    type_lower = clean_type.lower()

    if attrs.character_maximum_length is not None and type_lower not in _PG_NON_PARAMETRIC_TYPES:
        return f"{clean_type}({attrs.character_maximum_length})"
    if attrs.numeric_precision is not None and type_lower in ("decimal", "numeric"):
        if attrs.numeric_scale is not None:
            return f"{clean_type}({attrs.numeric_precision}, {attrs.numeric_scale})"
        return f"{clean_type}({attrs.numeric_precision})"
    return clean_type


def format_pg_column_definition(col_name: str, attrs: ColumnAttributes) -> str:
    """Format PostgreSQL column definition clause."""
    quoted_col = quote_identifier(col_name)
    type_str = format_pg_data_type(attrs)
    nullability = "NULL" if attrs.is_nullable else "NOT NULL"
    return f"{quoted_col} {type_str} {nullability}"


def generate_pg_script(
    target_profile: ConnectionProfile,
    missing_tables: Sequence[tuple[str, str, Sequence[tuple[str, ColumnAttributes]]]],
    missing_columns: Sequence[tuple[str, str, str, ColumnAttributes]],
    discrepant_columns: Sequence[tuple[str, str, str, ColumnAttributes, ColumnAttributes]],
) -> str:
    """Generate a complete, executable PostgreSQL DDL migration script wrapped in a transaction."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "-- ===========================================================================",
        "-- SCRIPT DE MIGRACIÓN/CORRECCIÓN DE ESQUEMA POSTGRESQL",
        f"-- Perfil Destino: {target_profile.name}",
        f"-- Generado el: {timestamp}",
        "-- ===========================================================================",
        "",
        "BEGIN;",
        "",
    ]

    # Create missing tables
    if missing_tables:
        lines.append("-- ---------------------------------------------------------------------------")
        lines.append("-- 1. CREACIÓN DE TABLAS FALTANTES")
        lines.append("-- ---------------------------------------------------------------------------")
        for schema, table, columns in missing_tables:
            quoted_table = f"{quote_identifier(schema)}.{quote_identifier(table)}"
            lines.append(f"CREATE TABLE IF NOT EXISTS {quoted_table} (")
            col_defs = [f"    {format_pg_column_definition(cname, attrs)}" for cname, attrs in columns]
            lines.append(",\n".join(col_defs))
            lines.append(");")
            lines.append("")

    # Add missing columns
    if missing_columns:
        lines.append("-- ---------------------------------------------------------------------------")
        lines.append("-- 2. ADICIÓN DE COLUMNAS FALTANTES")
        lines.append("-- ---------------------------------------------------------------------------")
        for schema, table, col_name, attrs in missing_columns:
            quoted_table = f"{quote_identifier(schema)}.{quote_identifier(table)}"
            col_def = format_pg_column_definition(col_name, attrs)
            lines.append(f"ALTER TABLE {quoted_table} ADD COLUMN IF NOT EXISTS {col_def};")
        lines.append("")

    # Alter discrepant columns
    if discrepant_columns:
        lines.append("-- ---------------------------------------------------------------------------")
        lines.append("-- 3. MODIFICACIÓN DE COLUMNAS CON DISCREPANCIAS")
        lines.append("-- ---------------------------------------------------------------------------")
        for schema, table, col_name, baseline_attrs, target_attrs in discrepant_columns:
            quoted_table = f"{quote_identifier(schema)}.{quote_identifier(table)}"
            quoted_col = quote_identifier(col_name)

            baseline_type_str = format_pg_data_type(baseline_attrs)
            target_type_str = format_pg_data_type(target_attrs)

            # Emit TYPE alter only if type or attributes changed
            if baseline_type_str.lower() != target_type_str.lower():
                lines.append(
                    f"ALTER TABLE {quoted_table} ALTER COLUMN {quoted_col} TYPE {target_type_str} USING CAST({quoted_col} AS {target_type_str});"
                )

            # Emit NULLABILITY alter only if nullability changed
            if baseline_attrs.is_nullable != target_attrs.is_nullable:
                if target_attrs.is_nullable:
                    lines.append(f"ALTER TABLE {quoted_table} ALTER COLUMN {quoted_col} DROP NOT NULL;")
                else:
                    lines.append(f"ALTER TABLE {quoted_table} ALTER COLUMN {quoted_col} SET NOT NULL;")
        lines.append("")

    lines.append("COMMIT;")
    lines.append("")
    return "\n".join(lines)
