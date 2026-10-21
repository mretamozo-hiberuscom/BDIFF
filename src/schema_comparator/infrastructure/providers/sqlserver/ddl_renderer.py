"""T-SQL DDL script generator for SQL Server microservice schema consolidation."""

import datetime
import re
from dataclasses import dataclass, replace

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.comparison.models import ColumnAttributes

# UTF-8 with BOM: SSMS and sqlcmd on Windows detect it without `-f 65001`
# and do not misread accented identifiers as the ANSI code page.
SQL_SCRIPT_ENCODING = "utf-8-sig"

# A schema change waiting for a lock queues every later query on the table;
# past this wait the script aborts and rolls back instead.
LOCK_TIMEOUT_MS = 30000

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
    pattern = re.compile(
        r"(?:database|initial catalog|db)\s*=\s*([^;]+)", re.IGNORECASE
    )
    match = pattern.search(connection_string)
    if match:
        return match.group(1).strip().strip("'\"[]").strip()
    return None


def format_sql_column_definition(attrs: ColumnAttributes) -> str:
    """Format column attributes to their corresponding SQL Server (T-SQL) definition."""
    clean_type = re.sub(r"\s*\(.*\)", "", attrs.data_type).strip()
    data_type_lower = clean_type.lower()

    if (
        attrs.character_maximum_length is not None
        and data_type_lower not in _NON_PARAMETRIC_TYPES
    ):
        size = (
            "MAX"
            if attrs.character_maximum_length == -1
            else str(attrs.character_maximum_length)
        )
        type_str = f"{clean_type}({size})"
    elif attrs.numeric_precision is not None and data_type_lower in (
        "decimal",
        "numeric",
    ):
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
    if clean_type in (
        "date",
        "datetime",
        "datetime2",
        "smalldatetime",
        "datetimeoffset",
    ):
        return "'1900-01-01'"
    if clean_type == "uniqueidentifier":
        return "'00000000-0000-0000-0000-000000000000'"
    if clean_type in ("varbinary", "binary", "image"):
        return "0x00"
    return "''"


@dataclass(frozen=True)
class _Position:
    """Where a step sits in the script; names its label and skip flag."""

    number: int
    total: int

    def label(self, title: str) -> str:
        return f"Paso {self.number}/{self.total}: {title}"

    @property
    def skip(self) -> str:
        return f"@skip_{self.number}"


@dataclass(frozen=True)
class _Step:
    """One change, rendered in three phases: `check` runs before anything
    changes (sets the skip flag when already applied, or aborts), `apply`
    makes the change, `verify` must hold before the COMMIT."""

    label: str
    check: str
    apply: str
    verify: str


def _qualified(*names: str) -> str:
    return ".".join(f"[{_escape_ident(name)}]" for name in names)


def _throw(number: int, text: str) -> str:
    # THROW treats `%` as a format character.
    message = _escape_literal(text).replace("%", "%%")
    return f"THROW {number}, N'{message}', 1;"


def _table_exists(schema: str, table: str) -> str:
    return (
        f"OBJECT_ID(N'{_escape_literal(_qualified(schema, table))}', N'U') IS NOT NULL"
    )


def _columns_where(schema: str, table: str, column: str | None = None) -> str:
    conditions = [
        f"TABLE_SCHEMA = N'{_escape_literal(schema)}'",
        f"TABLE_NAME = N'{_escape_literal(table)}'",
    ]
    if column is not None:
        conditions.append(f"COLUMN_NAME = N'{_escape_literal(column)}'")
    return " AND ".join(conditions)


def _column_exists(schema: str, table: str, column: str) -> str:
    return (
        "EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS "
        f"WHERE {_columns_where(schema, table, column)})"
    )


def _column_is(schema: str, table: str, column: str, attrs: ColumnAttributes) -> str:
    """True when the column is defined as `format_sql_column_definition`
    renders `attrs`, read from INFORMATION_SCHEMA like the extraction."""
    data_type = re.sub(r"\s*\(.*\)", "", attrs.data_type).strip().lower()
    conditions = [
        _columns_where(schema, table, column),
        f"DATA_TYPE = N'{_escape_literal(data_type)}'",
        f"IS_NULLABLE = '{'YES' if attrs.is_nullable else 'NO'}'",
    ]
    if (
        attrs.character_maximum_length is not None
        and data_type not in _NON_PARAMETRIC_TYPES
    ):
        conditions.append(
            f"CHARACTER_MAXIMUM_LENGTH = {int(attrs.character_maximum_length)}"
        )
    if data_type in ("decimal", "numeric") and attrs.numeric_precision is not None:
        conditions.append(f"NUMERIC_PRECISION = {int(attrs.numeric_precision)}")
        conditions.append(f"NUMERIC_SCALE = {int(attrs.numeric_scale or 0)}")
    return (
        "EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE "
        + " AND ".join(conditions)
        + ")"
    )


def _table_is(schema: str, table: str, columns) -> str:
    """True when the table has exactly `columns`, each as defined."""
    parts = [
        _table_exists(schema, table),
        "(SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
        f"WHERE {_columns_where(schema, table)}) = {len(columns)}",
        *(_column_is(schema, table, c.name, c.attributes) for c in columns),
    ]
    return "\n    AND ".join(parts)


def _create_table_step(tres, pos: _Position) -> _Step:
    table = _qualified(tres.schema_name, tres.table_name)
    label = pos.label(f"crear la tabla {table}")
    col_defs = ",\n".join(
        f"    [{_escape_ident(c.name)}] {format_sql_column_definition(c.attributes)}"
        for c in tres.columns
    )
    target = _table_is(tres.schema_name, tres.table_name, tres.columns)
    return _Step(
        label=label,
        check=(
            f"IF {_table_exists(tres.schema_name, tres.table_name)}\n"
            "BEGIN\n"
            f"    IF {target}\n"
            f"        SET {pos.skip} = 1;\n"
            "    ELSE\n"
            "        "
            + _throw(
                50001,
                f"{label}: la tabla ya existe con otra definicion; "
                "vuelve a comparar antes de aplicar.",
            )
            + "\nEND"
        ),
        apply=(
            f"CREATE TABLE {table} (\n{col_defs}\n);\n"
            f"PRINT N'Tabla {_escape_literal(table)} creada con exito.';"
        ),
        verify=target,
    )


def _drop_table_step(tdel, pos: _Position) -> _Step:
    table = _qualified(tdel.schema_name, tdel.table_name)
    table_lit = _escape_literal(table)
    exists = _table_exists(tdel.schema_name, tdel.table_name)
    var = f"@fk_sql_{pos.number}"
    return _Step(
        label=pos.label(f"eliminar la tabla {table}"),
        check=f"IF NOT ({exists})\n    SET {pos.skip} = 1;",
        apply=(
            f"DECLARE {var} NVARCHAR(MAX) = N'';\n"
            f"SELECT {var} += N'ALTER TABLE ' + QUOTENAME(s.name) + N'.' + QUOTENAME(o.name) + N' DROP CONSTRAINT ' + QUOTENAME(fk.name) + N';' + CHAR(13)\n"
            "FROM sys.foreign_keys fk\n"
            "JOIN sys.objects o ON fk.parent_object_id = o.object_id\n"
            "JOIN sys.schemas s ON o.schema_id = s.schema_id\n"
            f"WHERE fk.referenced_object_id = OBJECT_ID(N'{table_lit}');\n"
            f"IF {var} <> N'' EXEC sp_executesql {var};\n"
            f"DROP TABLE {table};\n"
            f"PRINT N'Tabla {table_lit} eliminada con exito.';"
        ),
        verify=f"NOT ({exists})",
    )


def _drop_column_step(cdel, pos: _Position) -> _Step:
    table = _qualified(cdel.schema_name, cdel.table_name)
    table_lit = _escape_literal(table)
    col_esc = _escape_ident(cdel.column_name)
    col_lit = _escape_literal(cdel.column_name)
    exists = _column_exists(cdel.schema_name, cdel.table_name, cdel.column_name)
    v = pos.number
    return _Step(
        label=pos.label(
            f"eliminar la columna {_qualified(cdel.schema_name, cdel.table_name, cdel.column_name)}"
        ),
        check=f"IF NOT {exists}\n    SET {pos.skip} = 1;",
        apply=(
            f"DECLARE @col_fk_sql_{v} NVARCHAR(MAX) = N'';\n"
            f"SELECT @col_fk_sql_{v} += N'ALTER TABLE ' + QUOTENAME(s.name) + N'.' + QUOTENAME(o.name) + N' DROP CONSTRAINT ' + QUOTENAME(fk.name) + N';' + CHAR(13)\n"
            "FROM (\n"
            "    SELECT DISTINCT fk.object_id, fk.name, fk.parent_object_id\n"
            "    FROM sys.foreign_keys fk\n"
            "    JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id\n"
            "    JOIN sys.columns c ON ((c.object_id = fkc.parent_object_id AND c.column_id = fkc.parent_column_id) OR (c.object_id = fkc.referenced_object_id AND c.column_id = fkc.referenced_column_id))\n"
            f"    WHERE (fkc.parent_object_id = OBJECT_ID(N'{table_lit}') OR fkc.referenced_object_id = OBJECT_ID(N'{table_lit}'))\n"
            f"      AND c.object_id = OBJECT_ID(N'{table_lit}')\n"
            f"      AND c.name = N'{col_lit}'\n"
            ") fk\n"
            "JOIN sys.objects o ON fk.parent_object_id = o.object_id\n"
            "JOIN sys.schemas s ON o.schema_id = s.schema_id;\n"
            f"IF @col_fk_sql_{v} <> N'' EXEC sp_executesql @col_fk_sql_{v};\n"
            "\n"
            f"DECLARE @key_sql_{v} NVARCHAR(MAX) = N'';\n"
            f"SELECT @key_sql_{v} += N'ALTER TABLE ' + QUOTENAME(s.name) + N'.' + QUOTENAME(t.name) + N' DROP CONSTRAINT ' + QUOTENAME(kc.name) + N';' + CHAR(13)\n"
            "FROM sys.key_constraints kc\n"
            "JOIN sys.tables t ON kc.parent_object_id = t.object_id\n"
            "JOIN sys.schemas s ON t.schema_id = s.schema_id\n"
            "JOIN sys.index_columns ic ON kc.parent_object_id = ic.object_id AND kc.unique_index_id = ic.index_id\n"
            "JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id\n"
            f"WHERE t.object_id = OBJECT_ID(N'{table_lit}')\n"
            f"  AND c.name = N'{col_lit}';\n"
            f"IF @key_sql_{v} <> N'' EXEC sp_executesql @key_sql_{v};\n"
            "\n"
            f"DECLARE @idx_sql_{v} NVARCHAR(MAX) = N'';\n"
            f"SELECT @idx_sql_{v} += N'DROP INDEX ' + QUOTENAME(i.name) + N' ON ' + QUOTENAME(s.name) + N'.' + QUOTENAME(t.name) + N';' + CHAR(13)\n"
            "FROM (\n"
            "    SELECT DISTINCT i.object_id, i.name\n"
            "    FROM sys.indexes i\n"
            "    JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id\n"
            "    JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id\n"
            "    WHERE i.is_primary_key = 0 AND i.is_unique_constraint = 0 AND i.name IS NOT NULL\n"
            f"      AND i.object_id = OBJECT_ID(N'{table_lit}')\n"
            f"      AND c.name = N'{col_lit}'\n"
            ") i\n"
            "JOIN sys.tables t ON i.object_id = t.object_id\n"
            "JOIN sys.schemas s ON t.schema_id = s.schema_id;\n"
            f"IF @idx_sql_{v} <> N'' EXEC sp_executesql @idx_sql_{v};\n"
            "\n"
            f"DECLARE @chk_sql_{v} NVARCHAR(MAX) = N'';\n"
            f"SELECT @chk_sql_{v} += N'ALTER TABLE ' + QUOTENAME(s.name) + N'.' + QUOTENAME(t.name) + N' DROP CONSTRAINT ' + QUOTENAME(cc.name) + N';' + CHAR(13)\n"
            "FROM (\n"
            "    SELECT DISTINCT cc.object_id, cc.name, cc.parent_object_id\n"
            "    FROM sys.check_constraints cc\n"
            "    LEFT JOIN sys.columns c ON cc.parent_object_id = c.object_id AND cc.parent_column_id = c.column_id\n"
            "    LEFT JOIN sys.sql_expression_dependencies sed ON cc.object_id = sed.referencing_id AND sed.referenced_id = cc.parent_object_id\n"
            "    LEFT JOIN sys.columns c2 ON sed.referenced_id = c2.object_id AND sed.referenced_minor_id = c2.column_id\n"
            f"    WHERE cc.parent_object_id = OBJECT_ID(N'{table_lit}')\n"
            f"      AND (c.name = N'{col_lit}' OR c2.name = N'{col_lit}')\n"
            ") cc\n"
            "JOIN sys.tables t ON cc.parent_object_id = t.object_id\n"
            "JOIN sys.schemas s ON t.schema_id = s.schema_id;\n"
            f"IF @chk_sql_{v} <> N'' EXEC sp_executesql @chk_sql_{v};\n"
            "\n"
            f"DECLARE @def_sql_{v} NVARCHAR(MAX) = N'';\n"
            f"SELECT @def_sql_{v} += N'ALTER TABLE ' + QUOTENAME(s.name) + N'.' + QUOTENAME(t.name) + N' DROP CONSTRAINT ' + QUOTENAME(dc.name) + N';' + CHAR(13)\n"
            "FROM sys.default_constraints dc\n"
            "JOIN sys.tables t ON dc.parent_object_id = t.object_id\n"
            "JOIN sys.schemas s ON t.schema_id = s.schema_id\n"
            "JOIN sys.columns c ON dc.parent_object_id = c.object_id AND dc.parent_column_id = c.column_id\n"
            f"WHERE t.object_id = OBJECT_ID(N'{table_lit}')\n"
            f"  AND c.name = N'{col_lit}';\n"
            f"IF @def_sql_{v} <> N'' EXEC sp_executesql @def_sql_{v};\n"
            "\n"
            f"ALTER TABLE {table} DROP COLUMN [{col_esc}];\n"
            f"PRINT N'Columna [{_escape_literal(col_esc)}] eliminada con exito de {table_lit}.';"
        ),
        verify=f"NOT {exists}",
    )


def _add_column_step(res, pos: _Position) -> _Step:
    table = _qualified(res.schema_name, res.table_name)
    column = _qualified(res.schema_name, res.table_name, res.column_name)
    label = pos.label(f"agregar la columna {column}")
    col_esc = _escape_ident(res.column_name)
    attrs = res.target_attributes
    col_def = format_sql_column_definition(attrs)
    if attrs.is_nullable:
        apply = f"ALTER TABLE {table} ADD [{col_esc}] {col_def};\n"
    else:
        # Dynamic SQL: a statement naming the new column would not compile
        # in the same batch that adds it.
        nullable_def = format_sql_column_definition(replace(attrs, is_nullable=True))
        backfill = _get_default_backfill_literal(attrs)
        statements = (
            f"ALTER TABLE {table} ADD [{col_esc}] {nullable_def};",
            f"UPDATE {table} SET [{col_esc}] = {backfill} WHERE [{col_esc}] IS NULL;",
            f"ALTER TABLE {table} ALTER COLUMN [{col_esc}] {col_def};",
        )
        apply = "".join(
            f"EXEC sys.sp_executesql N'{_escape_literal(sql)}';\n" for sql in statements
        )
    target = _column_is(res.schema_name, res.table_name, res.column_name, attrs)
    return _Step(
        label=label,
        check=(
            f"IF {_column_exists(res.schema_name, res.table_name, res.column_name)}\n"
            "BEGIN\n"
            f"    IF {target}\n"
            f"        SET {pos.skip} = 1;\n"
            "    ELSE\n"
            "        "
            + _throw(
                50001,
                f"{label}: la columna ya existe con otra definicion; "
                "vuelve a comparar antes de aplicar.",
            )
            + "\nEND\n"
            f"ELSE IF NOT ({_table_exists(res.schema_name, res.table_name)})\n"
            "    " + _throw(50001, f"{label}: la tabla {table} no existe.")
        ),
        apply=apply
        + f"PRINT N'Columna [{_escape_literal(col_esc)}] agregada con exito a {_escape_literal(table)}.';",
        verify=target,
    )


def _modify_column_step(
    res, observed: ColumnAttributes | None, pos: _Position
) -> _Step:
    table = _qualified(res.schema_name, res.table_name)
    table_lit = _escape_literal(table)
    column = _qualified(res.schema_name, res.table_name, res.column_name)
    label = pos.label(f"modificar la columna {column}")
    col_esc = _escape_ident(res.column_name)
    col_print = _escape_literal(col_esc)
    attrs = res.target_attributes
    target = _column_is(res.schema_name, res.table_name, res.column_name, attrs)
    check = (
        f"IF {target}\n"
        f"    SET {pos.skip} = 1;\n"
        f"ELSE IF NOT {_column_exists(res.schema_name, res.table_name, res.column_name)}\n"
        "    " + _throw(50001, f"{label}: la columna no existe.")
    )
    if observed is not None:
        check += (
            "\nELSE IF NOT "
            f"{_column_is(res.schema_name, res.table_name, res.column_name, observed)}\n"
            "    "
            + _throw(
                50001,
                f"{label}: la columna difiere de lo comparado; "
                "vuelve a comparar antes de aplicar.",
            )
        )
    apply = ""
    if not attrs.is_nullable:
        backfill = _get_default_backfill_literal(attrs)
        apply = (
            f"IF EXISTS (SELECT 1 FROM {table} WHERE [{col_esc}] IS NULL)\n"
            "BEGIN\n"
            f"    UPDATE {table}\n"
            f"    SET [{col_esc}] = {backfill}\n"
            f"    WHERE [{col_esc}] IS NULL;\n"
            f"    PRINT N'Valores NULL en {table_lit}.[{col_print}] actualizados pre-ALTER.';\n"
            "END\n"
        )
    apply += (
        f"ALTER TABLE {table} ALTER COLUMN [{col_esc}] {format_sql_column_definition(attrs)};\n"
        f"PRINT N'Columna [{col_print}] de {table_lit} modificada con exito.';"
    )
    return _Step(label=label, check=check, apply=apply, verify=target)


def _indent(text: str, spaces: int) -> str:
    pad = " " * spaces
    return "\n".join(pad + line if line else line for line in text.splitlines())


def _render_steps(steps: list[_Step]) -> list[str]:
    if not steps:
        return ["    PRINT N'No se requieren cambios para este perfil.';"]
    flags = ", ".join(f"@skip_{n} bit = 0" for n in range(1, len(steps) + 1))
    lines = [
        f"    DECLARE {flags};",
        "",
        "    -- 1. Comprobaciones previas: todavia no se ha cambiado nada.",
    ]
    for step in steps:
        lines += [f"    -- {step.label}", _indent(step.check, 4)]
    lines += ["", "    -- 2. Cambios."]
    for n, step in enumerate(steps, 1):
        label = _escape_literal(step.label)
        lines += [
            f"    IF @skip_{n} = 0",
            "    BEGIN",
            f"        PRINT N'{label}';",
            _indent(step.apply, 8),
            "    END",
            "    ELSE",
            f"        PRINT N'{label} ya aplicado; se omite.';",
        ]
    lines += ["", "    -- 3. Verificacion final antes de confirmar."]
    for step in steps:
        lines += [
            f"    IF NOT ({_indent(step.verify, 4).lstrip()})",
            "        "
            + _throw(50002, f"{step.label}: no quedo aplicado; se deshace todo."),
        ]
    return lines


def _steps_for(
    profile_name: str,
    resolutions: list,
    table_resolutions: list,
    table_deletions: list,
    column_deletions: list,
) -> list[_Step]:
    builders = (
        [
            lambda pos, t=t: _create_table_step(t, pos)
            for t in table_resolutions
            if profile_name in t.profiles_to_update
        ]
        + [
            lambda pos, t=t: _drop_table_step(t, pos)
            for t in table_deletions
            if profile_name in t.profiles_to_update
        ]
        + [
            lambda pos, c=c: _drop_column_step(c, pos)
            for c in column_deletions
            if profile_name in c.profiles_to_update
        ]
        + [
            (
                lambda pos, r=r: (
                    _add_column_step(r, pos)
                    if r.is_missing_column
                    else _modify_column_step(
                        r, dict(r.observed_by_profile).get(profile_name), pos
                    )
                )
            )
            for r in resolutions
            if profile_name in r.profiles_to_update
        ]
    )
    total = len(builders)
    return [build(_Position(n, total)) for n, build in enumerate(builders, 1)]


def generate_ddl_for_profile(
    resolutions: list,
    profile: ConnectionProfile,
    timestamp: datetime.datetime | None = None,
    table_resolutions: list | None = None,
    table_deletions: list | None = None,
    column_deletions: list | None = None,
) -> str:
    """The profile's T-SQL script: one transaction that checks every step
    against the compared state before changing anything, applies the steps
    and verifies them before committing; any failure rolls everything back."""
    ts = timestamp or datetime.datetime.now()
    raw_db = extract_database_name(profile.connection_string)
    if not raw_db:
        raise ValueError(f"profile {profile.name!r} names no database")
    db_name = _escape_ident(raw_db)
    db_lit = _escape_literal(raw_db)
    steps = _steps_for(
        profile.name,
        resolutions or [],
        table_resolutions or [],
        table_deletions or [],
        column_deletions or [],
    )

    return "\n".join(
        [
            f"-- Script de corrección para la base de datos del perfil: {profile.name}",
            f"-- Generado por BDIFF el {ts.strftime('%Y-%m-%d %H:%M:%S')}",
            "--",
            "-- Todos los cambios van en una única transacción: primero se comprueba",
            "-- que cada objeto sigue como se comparó, después se aplican los cambios",
            "-- y se verifican antes de confirmar. Ante cualquier error se deshacen",
            "-- completos y la base queda como estaba.",
            "-- Ejecución:",
            '--   sqlcmd -S <servidor> -E -b -i "<este archivo>.sql"',
            "--     (-b detiene sqlcmd en el primer error y devuelve código de salida <> 0)",
            "--   SSMS: abrir el archivo y ejecutarlo completo (F5).",
            "-- Si la base activa no es la esperada, el script no ejecuta nada.",
            "",
            f"USE [{db_name}];",
            "GO",
            "",
            f"IF DB_NAME() <> N'{db_lit}'",
            "BEGIN",
            f"    RAISERROR(N'La base activa no es %s; no se aplica ningun cambio.', 16, 1, N'{db_lit}');",
            "    SET NOEXEC ON;",
            "END",
            "GO",
            "",
            "SET NOCOUNT ON;",
            "SET XACT_ABORT ON;",
            f"SET LOCK_TIMEOUT {LOCK_TIMEOUT_MS};",
            "SET NUMERIC_ROUNDABORT OFF;",
            "SET ANSI_PADDING, ANSI_WARNINGS, CONCAT_NULL_YIELDS_NULL, ARITHABORT, QUOTED_IDENTIFIER, ANSI_NULLS ON;",
            "GO",
            "",
            "BEGIN TRY",
            "    BEGIN TRANSACTION;",
            "",
            *_render_steps(steps),
            "",
            "    COMMIT TRANSACTION;",
            "    PRINT N'Transaccion confirmada con exito.';",
            "END TRY",
            "BEGIN CATCH",
            "    IF @@TRANCOUNT > 0",
            "        ROLLBACK TRANSACTION;",
            "    PRINT N'Transaccion abortada debido a un error; no se aplico ningun cambio.';",
            "    THROW;",
            "END CATCH;",
            "GO",
            "",
            "SET NOEXEC OFF;",
            "GO",
            "",
        ]
    )
