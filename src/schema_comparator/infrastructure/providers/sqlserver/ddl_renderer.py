"""T-SQL DDL script generator for SQL Server microservice schema consolidation."""

import datetime
import re

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.comparison.models import ColumnAttributes

_NON_PARAMETRIC_TYPES = {
    "bit",
    "int",
    "bigint",
    "smallint",
    "tinyint",
    "float",
    "real",
    "date",
    "datetime",
    "datetime2",
    "smalldatetime",
    "datetimeoffset",
    "time",
    "money",
    "smallmoney",
    "uniqueidentifier",
    "xml",
    "text",
    "ntext",
    "image",
}


def extract_database_name(connection_string: str) -> str | None:
    """Extract the database name (Initial Catalog or Database) from a SQL Server connection string."""
    pattern = re.compile(r'(?:database|initial catalog|db)\s*=\s*([^;]+)', re.IGNORECASE)
    match = pattern.search(connection_string)
    if match:
        return match.group(1).strip().strip("'\"[]").strip()
    return None


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


def _get_default_backfill_literal(attrs: ColumnAttributes) -> str:
    """Return a safe T-SQL literal to backfill NULL values when converting a column to NOT NULL."""
    if attrs.default_expression:
        expr = attrs.default_expression.strip()
        while expr.startswith("(") and expr.endswith(")") and len(expr) > 2:
            expr = expr[1:-1].strip()
        return expr if expr else "0"

    clean_type = re.sub(r"\s*\(.*\)", "", attrs.data_type).strip().lower()
    if clean_type in (
        "bit",
        "int",
        "bigint",
        "smallint",
        "tinyint",
        "decimal",
        "numeric",
        "float",
        "real",
        "money",
        "smallmoney",
    ):
        return "0"
    if clean_type in ("varchar", "nvarchar", "char", "nchar", "text", "ntext", "xml"):
        return "''"
    if clean_type == "time":
        return "'00:00:00'"
    if clean_type in ("date", "datetime", "datetime2", "smalldatetime", "datetimeoffset"):
        return "'1900-01-01'"
    if clean_type == "uniqueidentifier":
        return "'00000000-0000-0000-0000-000000000000'"
    if clean_type in ("varbinary", "binary", "image"):
        return "0x00"
    return "''"


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
            schema_print = _escape_literal(schema_esc)
            table_print = _escape_literal(table_esc)

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
                f"        PRINT 'Tabla [{schema_print}].[{table_print}] creada con exito.';\n"
                f"    END"
            )
            lines.append(sql)
            statements_added = True

    for idx, tdel in enumerate(table_deletions or []):
        if profile.name in tdel.profiles_to_update:
            schema_esc = _escape_ident(tdel.schema_name)
            table_esc = _escape_ident(tdel.table_name)
            schema_lit = _escape_literal(tdel.schema_name)
            table_lit = _escape_literal(tdel.table_name)
            schema_print = _escape_literal(schema_esc)
            table_print = _escape_literal(table_esc)
            var_suffix = f"t_{idx}"

            sql = (
                f"    IF EXISTS (\n"
                f"        SELECT 1\n"
                f"        FROM sys.objects o\n"
                f"        JOIN sys.schemas s ON o.schema_id = s.schema_id\n"
                f"        WHERE s.name = '{schema_lit}' AND o.name = '{table_lit}' AND o.type = 'U'\n"
                f"    )\n"
                f"    BEGIN\n"
                f"        DECLARE @fk_sql_{var_suffix} NVARCHAR(MAX) = N'';\n"
                f"        SELECT @fk_sql_{var_suffix} += N'ALTER TABLE ' + QUOTENAME(s.name) + N'.' + QUOTENAME(o.name) + N' DROP CONSTRAINT ' + QUOTENAME(fk.name) + N';' + CHAR(13)\n"
                f"        FROM sys.foreign_keys fk\n"
                f"        JOIN sys.objects o ON fk.parent_object_id = o.object_id\n"
                f"        JOIN sys.schemas s ON o.schema_id = s.schema_id\n"
                f"        WHERE fk.referenced_object_id = OBJECT_ID(N'[{schema_lit}].[{table_lit}]');\n"
                f"        IF @fk_sql_{var_suffix} <> N'' EXEC sp_executesql @fk_sql_{var_suffix};\n"
                f"        DROP TABLE [{schema_esc}].[{table_esc}];\n"
                f"        PRINT 'Tabla [{schema_print}].[{table_print}] eliminada con exito.';\n"
                f"    END"
            )
            lines.append(sql)
            statements_added = True

    for idx, cdel in enumerate(column_deletions or []):
        if profile.name in cdel.profiles_to_update:
            schema_esc = _escape_ident(cdel.schema_name)
            table_esc = _escape_ident(cdel.table_name)
            col_esc = _escape_ident(cdel.column_name)
            schema_lit = _escape_literal(cdel.schema_name)
            table_lit = _escape_literal(cdel.table_name)
            col_lit = _escape_literal(cdel.column_name)
            schema_print = _escape_literal(schema_esc)
            table_print = _escape_literal(table_esc)
            col_print = _escape_literal(col_esc)
            var_suffix = f"c_{idx}"

            sql = (
                f"    IF EXISTS (\n"
                f"        SELECT 1 \n"
                f"        FROM sys.columns c\n"
                f"        JOIN sys.objects o ON c.object_id = o.object_id\n"
                f"        JOIN sys.schemas s ON o.schema_id = s.schema_id\n"
                f"        WHERE s.name = '{schema_lit}' AND o.name = '{table_lit}' AND c.name = '{col_lit}'\n"
                f"    )\n"
                f"    BEGIN\n"
                f"        DECLARE @col_fk_sql_{var_suffix} NVARCHAR(MAX) = N'';\n"
                f"        SELECT @col_fk_sql_{var_suffix} += N'ALTER TABLE ' + QUOTENAME(s.name) + N'.' + QUOTENAME(o.name) + N' DROP CONSTRAINT ' + QUOTENAME(fk.name) + N';' + CHAR(13)\n"
                f"        FROM (\n"
                f"            SELECT DISTINCT fk.object_id, fk.name, fk.parent_object_id\n"
                f"            FROM sys.foreign_keys fk\n"
                f"            JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id\n"
                f"            JOIN sys.columns c ON ((c.object_id = fkc.parent_object_id AND c.column_id = fkc.parent_column_id) OR (c.object_id = fkc.referenced_object_id AND c.column_id = fkc.referenced_column_id))\n"
                f"            WHERE (fkc.parent_object_id = OBJECT_ID(N'[{schema_lit}].[{table_lit}]') OR fkc.referenced_object_id = OBJECT_ID(N'[{schema_lit}].[{table_lit}]'))\n"
                f"              AND c.object_id = OBJECT_ID(N'[{schema_lit}].[{table_lit}]')\n"
                f"              AND c.name = '{col_lit}'\n"
                f"        ) fk\n"
                f"        JOIN sys.objects o ON fk.parent_object_id = o.object_id\n"
                f"        JOIN sys.schemas s ON o.schema_id = s.schema_id;\n"
                f"        IF @col_fk_sql_{var_suffix} <> N'' EXEC sp_executesql @col_fk_sql_{var_suffix};\n"
                f"\n"
                f"        DECLARE @key_sql_{var_suffix} NVARCHAR(MAX) = N'';\n"
                f"        SELECT @key_sql_{var_suffix} += N'ALTER TABLE ' + QUOTENAME(s.name) + N'.' + QUOTENAME(t.name) + N' DROP CONSTRAINT ' + QUOTENAME(kc.name) + N';' + CHAR(13)\n"
                f"        FROM sys.key_constraints kc\n"
                f"        JOIN sys.tables t ON kc.parent_object_id = t.object_id\n"
                f"        JOIN sys.schemas s ON t.schema_id = s.schema_id\n"
                f"        JOIN sys.index_columns ic ON kc.parent_object_id = ic.object_id AND kc.unique_index_id = ic.index_id\n"
                f"        JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id\n"
                f"        WHERE t.object_id = OBJECT_ID(N'[{schema_lit}].[{table_lit}]')\n"
                f"          AND c.name = '{col_lit}';\n"
                f"        IF @key_sql_{var_suffix} <> N'' EXEC sp_executesql @key_sql_{var_suffix};\n"
                f"\n"
                f"        DECLARE @idx_sql_{var_suffix} NVARCHAR(MAX) = N'';\n"
                f"        SELECT @idx_sql_{var_suffix} += N'DROP INDEX ' + QUOTENAME(i.name) + N' ON ' + QUOTENAME(s.name) + N'.' + QUOTENAME(t.name) + N';' + CHAR(13)\n"
                f"        FROM (\n"
                f"            SELECT DISTINCT i.object_id, i.name\n"
                f"            FROM sys.indexes i\n"
                f"            JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id\n"
                f"            JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id\n"
                f"            WHERE i.is_primary_key = 0 AND i.is_unique_constraint = 0 AND i.name IS NOT NULL\n"
                f"              AND i.object_id = OBJECT_ID(N'[{schema_lit}].[{table_lit}]')\n"
                f"              AND c.name = '{col_lit}'\n"
                f"        ) i\n"
                f"        JOIN sys.tables t ON i.object_id = t.object_id\n"
                f"        JOIN sys.schemas s ON t.schema_id = s.schema_id;\n"
                f"        IF @idx_sql_{var_suffix} <> N'' EXEC sp_executesql @idx_sql_{var_suffix};\n"
                f"\n"
                f"        DECLARE @chk_sql_{var_suffix} NVARCHAR(MAX) = N'';\n"
                f"        SELECT @chk_sql_{var_suffix} += N'ALTER TABLE ' + QUOTENAME(s.name) + N'.' + QUOTENAME(t.name) + N' DROP CONSTRAINT ' + QUOTENAME(cc.name) + N';' + CHAR(13)\n"
                f"        FROM (\n"
                f"            SELECT DISTINCT cc.object_id, cc.name, cc.parent_object_id\n"
                f"            FROM sys.check_constraints cc\n"
                f"            LEFT JOIN sys.columns c ON cc.parent_object_id = c.object_id AND cc.parent_column_id = c.column_id\n"
                f"            LEFT JOIN sys.sql_expression_dependencies sed ON cc.object_id = sed.referencing_id AND sed.referenced_id = cc.parent_object_id\n"
                f"            LEFT JOIN sys.columns c2 ON sed.referenced_id = c2.object_id AND sed.referenced_minor_id = c2.column_id\n"
                f"            WHERE cc.parent_object_id = OBJECT_ID(N'[{schema_lit}].[{table_lit}]')\n"
                f"              AND (c.name = '{col_lit}' OR c2.name = '{col_lit}')\n"
                f"        ) cc\n"
                f"        JOIN sys.tables t ON cc.parent_object_id = t.object_id\n"
                f"        JOIN sys.schemas s ON t.schema_id = s.schema_id;\n"
                f"        IF @chk_sql_{var_suffix} <> N'' EXEC sp_executesql @chk_sql_{var_suffix};\n"
                f"\n"
                f"        DECLARE @def_sql_{var_suffix} NVARCHAR(MAX) = N'';\n"
                f"        SELECT @def_sql_{var_suffix} += N'ALTER TABLE ' + QUOTENAME(s.name) + N'.' + QUOTENAME(t.name) + N' DROP CONSTRAINT ' + QUOTENAME(dc.name) + N';' + CHAR(13)\n"
                f"        FROM sys.default_constraints dc\n"
                f"        JOIN sys.tables t ON dc.parent_object_id = t.object_id\n"
                f"        JOIN sys.schemas s ON t.schema_id = s.schema_id\n"
                f"        JOIN sys.columns c ON dc.parent_object_id = c.object_id AND dc.parent_column_id = c.column_id\n"
                f"        WHERE t.object_id = OBJECT_ID(N'[{schema_lit}].[{table_lit}]')\n"
                f"          AND c.name = '{col_lit}';\n"
                f"        IF @def_sql_{var_suffix} <> N'' EXEC sp_executesql @def_sql_{var_suffix};\n"
                f"\n"
                f"        ALTER TABLE [{schema_esc}].[{table_esc}] DROP COLUMN [{col_esc}];\n"
                f"        PRINT 'Columna [{col_print}] eliminada con exito de [{schema_print}].[{table_print}].';\n"
                f"    END"
            )
            lines.append(sql)
            statements_added = True

    for res in (resolutions or []):
        if profile.name in res.profiles_to_update:
            col_def = format_sql_column_definition(res.target_attributes)
            schema_esc = _escape_ident(res.schema_name)
            table_esc = _escape_ident(res.table_name)
            col_esc = _escape_ident(res.column_name)
            schema_lit = _escape_literal(res.schema_name)
            table_lit = _escape_literal(res.table_name)
            col_lit = _escape_literal(res.column_name)
            schema_print = _escape_literal(schema_esc)
            table_print = _escape_literal(table_esc)
            col_print = _escape_literal(col_esc)

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
                    f"        PRINT 'Columna [{col_print}] agregada con exito a [{schema_print}].[{table_print}].';\n"
                    f"    END"
                )
            else:
                backfill_block = ""
                if not res.target_attributes.is_nullable:
                    backfill_val = _get_default_backfill_literal(res.target_attributes)
                    backfill_block = (
                        f"        IF EXISTS (SELECT 1 FROM [{schema_esc}].[{table_esc}] WHERE [{col_esc}] IS NULL)\n"
                        f"        BEGIN\n"
                        f"            UPDATE [{schema_esc}].[{table_esc}]\n"
                        f"            SET [{col_esc}] = {backfill_val}\n"
                        f"            WHERE [{col_esc}] IS NULL;\n"
                        f"            PRINT 'Valores NULL en [{schema_print}].[{table_print}].[{col_print}] actualizados pre-ALTER.';\n"
                        f"        END\n"
                    )

                sql = (
                    f"    IF EXISTS (\n"
                    f"        SELECT 1 \n"
                    f"        FROM sys.columns c\n"
                    f"        JOIN sys.objects o ON c.object_id = o.object_id\n"
                    f"        JOIN sys.schemas s ON o.schema_id = s.schema_id\n"
                    f"        WHERE s.name = '{schema_lit}' AND o.name = '{table_lit}' AND c.name = '{col_lit}'\n"
                    f"    )\n"
                    f"    BEGIN\n"
                    f"{backfill_block}"
                    f"        ALTER TABLE [{schema_esc}].[{table_esc}] ALTER COLUMN [{col_esc}] {col_def};\n"
                    f"        PRINT 'Columna [{col_print}] de [{schema_print}].[{table_print}] modificada con exito.';\n"
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
        "",
    ])

    return "\n".join(lines)
