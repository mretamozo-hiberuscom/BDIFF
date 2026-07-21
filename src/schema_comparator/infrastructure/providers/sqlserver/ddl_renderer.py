"""SQL Server T-SQL DDL renderer and consolidation helpers."""

import datetime
import re
from pathlib import Path

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.comparison.models import ColumnAttributes, NamedColumnAttributes


def extract_database_name(connection_string: str) -> str | None:
    """Extract the database name (Initial Catalog or Database) from a SQL Server connection string."""
    pattern = re.compile(r'(?:database|initial catalog|db)\s*=\s*([^;]+)', re.IGNORECASE)
    match = pattern.search(connection_string)
    if match:
        return match.group(1).strip()
    return None


_NON_PARAMETRIC_TYPES = {
    "int",
    "bigint",
    "smallint",
    "tinyint",
    "bit",
    "date",
    "datetime",
    "smalldatetime",
    "real",
    "money",
    "smallmoney",
    "uniqueidentifier",
    "xml",
    "text",
    "ntext",
    "image",
}


def format_sql_column_definition(attrs: ColumnAttributes) -> str:
    """Format column attributes to their corresponding SQL Server (T-SQL) definition."""
    clean_type = re.sub(r"\s*\(.*\)", "", attrs.data_type).strip()
    data_type_lower = clean_type.lower()

    if attrs.character_maximum_length is not None and data_type_lower not in _NON_PARAMETRIC_TYPES:
        size = "MAX" if attrs.character_maximum_length == -1 else str(attrs.character_maximum_length)
        type_str = f"{clean_type}({size})"
    elif attrs.numeric_precision is not None and data_type_lower in ("decimal", "numeric"):
        if attrs.numeric_scale is not None:
            type_str = f"{clean_type}({attrs.numeric_precision}, {attrs.numeric_scale})"
        else:
            type_str = f"{clean_type}({attrs.numeric_precision})"
    else:
        type_str = clean_type

    nullability = "NULL" if attrs.is_nullable else "NOT NULL"
    return f"{type_str} {nullability}"



def _escape_ident(identifier: str) -> str:
    """Escape closing bracket for T-SQL bracketed identifiers."""
    return identifier.replace("]", "]]")


def _escape_literal(literal: str) -> str:
    """Escape single quote for T-SQL string literals."""
    return literal.replace("'", "''")


def generate_ddl_for_profile(
    resolutions: list,
    profile: ConnectionProfile,
    timestamp: datetime.datetime | None = None,
    table_resolutions: list | None = None,
    table_deletions: list | None = None,
    column_deletions: list | None = None,
) -> str:
    """Generate transactional, idempotent, enterprise-grade T-SQL scripts for a profile."""
    ts = timestamp or datetime.datetime.now()
    raw_db = extract_database_name(profile.connection_string) or profile.name
    db_name = _escape_ident(raw_db)

    lines = [
        f"-- Script de corrección para la base de datos del perfil: {profile.name}",
        f"-- Generado por BDIFF el {ts.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"USE [{db_name}];",
        "GO",
        "",
        "SET NUMERIC_ROUNDABORT OFF;",
        "SET ANSI_PADDING, ANSI_WARNINGS, CONCAT_NULL_YIELDS_NULL, ARITHABORT, QUOTED_IDENTIFIER, ANSI_NULLS ON;",
        "GO",
        "",
        "BEGIN TRANSACTION;",
        "BEGIN TRY",
    ]

    statements_added = False

    for tres in (table_resolutions or []):
        if profile.name in tres.profiles_to_update:
            schema_esc = _escape_ident(tres.schema_name)
            table_esc = _escape_ident(tres.table_name)
            schema_lit = _escape_literal(tres.schema_name)
            table_lit = _escape_literal(tres.table_name)

            col_defs = []
            for ncol in tres.columns:
                col_def = format_sql_column_definition(ncol.attributes)
                col_esc = _escape_ident(ncol.name)
                col_defs.append(f"        [{col_esc}] {col_def}")
            col_list = ",\n".join(col_defs)

            sql = (
                f"    IF NOT EXISTS (\n"
                f"        SELECT 1\n"
                f"        FROM sys.objects o\n"
                f"        JOIN sys.schemas s ON o.schema_id = s.schema_id\n"
                f"        WHERE s.name = '{schema_lit}' AND o.name = '{table_lit}' AND o.type = 'U'\n"
                f"    )\n"
                f"    BEGIN\n"
                f"        CREATE TABLE [{schema_esc}].[{table_esc}] (\n"
                f"{col_list}\n"
                f"        );\n"
                f"        PRINT 'Tabla [{schema_esc}].[{table_esc}] creada con exito.';\n"
                f"    END"
            )
            lines.append(sql)
            statements_added = True

    for deletion in (table_deletions or []):
        if profile.name in deletion.profiles_to_update:
            schema_esc = _escape_ident(deletion.schema_name)
            table_esc = _escape_ident(deletion.table_name)
            schema_lit = _escape_literal(deletion.schema_name)
            table_lit = _escape_literal(deletion.table_name)

            sql = (
                f"    IF EXISTS (\n"
                f"        SELECT 1\n"
                f"        FROM sys.objects o\n"
                f"        JOIN sys.schemas s ON o.schema_id = s.schema_id\n"
                f"        WHERE s.name = '{schema_lit}' AND o.name = '{table_lit}' AND o.type = 'U'\n"
                f"    )\n"
                f"    BEGIN\n"
                f"        DROP TABLE [{schema_esc}].[{table_esc}];\n"
                f"        PRINT 'Tabla [{schema_esc}].[{table_esc}] eliminada con exito.';\n"
                f"    END"
            )
            lines.append(sql)
            statements_added = True

    for deletion in (column_deletions or []):
        if profile.name in deletion.profiles_to_update:
            schema_esc = _escape_ident(deletion.schema_name)
            table_esc = _escape_ident(deletion.table_name)
            col_esc = _escape_ident(deletion.column_name)
            schema_lit = _escape_literal(deletion.schema_name)
            table_lit = _escape_literal(deletion.table_name)
            col_lit = _escape_literal(deletion.column_name)

            sql = (
                f"    IF EXISTS (\n"
                f"        SELECT 1\n"
                f"        FROM sys.columns c\n"
                f"        JOIN sys.objects o ON c.object_id = o.object_id\n"
                f"        JOIN sys.schemas s ON o.schema_id = s.schema_id\n"
                f"        WHERE s.name = '{schema_lit}' AND o.name = '{table_lit}' AND c.name = '{col_lit}'\n"
                f"    )\n"
                f"    BEGIN\n"
                f"        ALTER TABLE [{schema_esc}].[{table_esc}] DROP COLUMN [{col_esc}];\n"
                f"        PRINT 'Columna [{col_esc}] eliminada con exito de [{schema_esc}].[{table_esc}].';\n"
                f"    END"
            )
            lines.append(sql)
            statements_added = True

    for res in resolutions:
        if profile.name in res.profiles_to_update:
            col_def = format_sql_column_definition(res.target_attributes)
            schema_esc = _escape_ident(res.schema_name)
            table_esc = _escape_ident(res.table_name)
            col_esc = _escape_ident(res.column_name)
            schema_lit = _escape_literal(res.schema_name)
            table_lit = _escape_literal(res.table_name)
            col_lit = _escape_literal(res.column_name)

            if res.is_missing_column:
                sql = (
                    f"    IF NOT EXISTS (\n"
                    f"        SELECT 1 \n"
                    f"        FROM sys.columns c\n"
                    f"        JOIN sys.objects o ON c.object_id = o.object_id\n"
                    f"        JOIN sys.schemas s ON o.schema_id = s.schema_id\n"
                    f"        WHERE s.name = '{schema_lit}' AND o.name = '{table_lit}' AND c.name = '{col_lit}'\n"
                    f"    )\n"
                    f"    BEGIN\n"
                    f"        ALTER TABLE [{schema_esc}].[{table_esc}] ADD [{col_esc}] {col_def};\n"
                    f"        PRINT 'Columna [{col_esc}] agregada con exito a [{schema_esc}].[{table_esc}].';\n"
                    f"    END"
                )
            else:
                sql = (
                    f"    IF EXISTS (\n"
                    f"        SELECT 1 \n"
                    f"        FROM sys.columns c\n"
                    f"        JOIN sys.objects o ON c.object_id = o.object_id\n"
                    f"        JOIN sys.schemas s ON o.schema_id = s.schema_id\n"
                    f"        WHERE s.name = '{schema_lit}' AND o.name = '{table_lit}' AND c.name = '{col_lit}'\n"
                    f"    )\n"
                    f"    BEGIN\n"
                    f"        ALTER TABLE [{schema_esc}].[{table_esc}] ALTER COLUMN [{col_esc}] {col_def};\n"
                    f"        PRINT 'Columna [{col_esc}] de [{schema_esc}].[{table_esc}] modificada con exito.';\n"
                    f"    END"
                )
            lines.append(sql)
            statements_added = True

    if not statements_added:
        lines.append("    PRINT 'No se requieren cambios para este perfil.';")

    lines.extend([
        "",
        "    COMMIT TRANSACTION;",
        "    PRINT 'Transaccion confirmada con exito.';",
        "END TRY",
        "BEGIN CATCH",
        "    IF @@TRANCOUNT > 0",
        "    BEGIN",
        "        ROLLBACK TRANSACTION;",
        "        PRINT 'Transaccion abortada debido a un error.';",
        "    END",
        "    DECLARE @ErrorMessage NVARCHAR(4000) = ERROR_MESSAGE();",
        "    DECLARE @ErrorSeverity INT = ERROR_SEVERITY();",
        "    DECLARE @ErrorState INT = ERROR_STATE();",
        "    RAISERROR(@ErrorMessage, @ErrorSeverity, @ErrorState);",
        "END CATCH;",
        "GO",
    ])

    return "\n".join(lines) + "\n"
