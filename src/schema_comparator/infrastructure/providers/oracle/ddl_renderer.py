"""Oracle DDL script generator."""

import datetime
import re
from typing import Sequence

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.comparison.models import ColumnAttributes


def quote_identifier(identifier: str) -> str:
    """Quote an Oracle identifier using double quotes."""
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


def format_oracle_data_type(attrs: ColumnAttributes) -> str:
    """Format Oracle data type string including length, precision, and scale."""
    clean_type = re.sub(r"\s*\(.*\)", "", attrs.data_type).strip()
    type_upper = clean_type.upper()

    if attrs.character_maximum_length is not None and type_upper in ("VARCHAR2", "CHAR", "NVARCHAR2", "RAW"):
        return f"{type_upper}({attrs.character_maximum_length})"
    if attrs.numeric_precision is not None and type_upper in ("NUMBER", "FLOAT"):
        if attrs.numeric_scale is not None:
            return f"{type_upper}({attrs.numeric_precision}, {attrs.numeric_scale})"
        return f"{type_upper}({attrs.numeric_precision})"
    if "(" in attrs.data_type and ")" in attrs.data_type:
        return attrs.data_type
    return type_upper


def format_oracle_column_definition(col_name: str, attrs: ColumnAttributes) -> str:
    """Format Oracle column definition clause."""
    quoted_col = quote_identifier(col_name)
    type_str = format_oracle_data_type(attrs)
    nullability = "NULL" if attrs.is_nullable else "NOT NULL"

    parts = [quoted_col, type_str]

    is_ident = getattr(attrs, "is_identity", False)
    default_expr = getattr(attrs, "default_expression", None)

    if is_ident:
        parts.append("GENERATED ALWAYS AS IDENTITY")
    elif default_expr and "ISEQ$$" not in default_expr.upper() and ".NEXTVAL" not in default_expr.upper():
        parts.append(f"DEFAULT {default_expr}")

    parts.append(nullability)

    return " ".join(parts)


def generate_oracle_script(
    target_profile: ConnectionProfile,
    missing_tables: Sequence[tuple[str, str, Sequence[tuple[str, ColumnAttributes]]]],
    missing_columns: Sequence[tuple[str, str, str, ColumnAttributes]],
    discrepant_columns: Sequence[tuple[str, str, str, ColumnAttributes, ColumnAttributes]],
) -> str:
    """Generate an executable Oracle DDL migration script."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "-- ===========================================================================",
        "-- SCRIPT DE MIGRACIÓN/CORRECCIÓN DE ESQUEMA ORACLE",
        f"-- Perfil Destino: {target_profile.name}",
        f"-- Generado el: {timestamp}",
        "-- ===========================================================================",
        "",
    ]

    # Create missing tables
    if missing_tables:
        lines.append("-- ---------------------------------------------------------------------------")
        lines.append("-- 1. CREACIÓN DE TABLAS FALTANTES")
        lines.append("-- ---------------------------------------------------------------------------")
        for schema, table, columns in missing_tables:
            table_ref = f"{quote_identifier(schema)}.{quote_identifier(table)}" if schema else quote_identifier(table)
            lines.append(f"CREATE TABLE {table_ref} (")
            col_defs = [f"    {format_oracle_column_definition(cname, attrs)}" for cname, attrs in columns]
            lines.append(",\n".join(col_defs))
            lines.append(");")
            lines.append("")

    # Add missing columns
    if missing_columns:
        lines.append("-- ---------------------------------------------------------------------------")
        lines.append("-- 2. ADICIÓN DE COLUMNAS FALTANTES")
        lines.append("-- ---------------------------------------------------------------------------")
        for schema, table, col_name, attrs in missing_columns:
            table_ref = f"{quote_identifier(schema)}.{quote_identifier(table)}" if schema else quote_identifier(table)
            col_def = format_oracle_column_definition(col_name, attrs)
            lines.append(f"ALTER TABLE {table_ref} ADD ({col_def});")
        lines.append("")

    # Alter discrepant columns
    if discrepant_columns:
        lines.append("-- ---------------------------------------------------------------------------")
        lines.append("-- 3. MODIFICACIÓN DE COLUMNAS CON DISCREPANCIAS")
        lines.append("-- ---------------------------------------------------------------------------")
        for schema, table, col_name, _baseline_attrs, target_attrs in discrepant_columns:
            table_ref = f"{quote_identifier(schema)}.{quote_identifier(table)}" if schema else quote_identifier(table)
            col_def = format_oracle_column_definition(col_name, target_attrs)
            lines.append(f"ALTER TABLE {table_ref} MODIFY ({col_def});")
        lines.append("")

    return "\n".join(lines)
