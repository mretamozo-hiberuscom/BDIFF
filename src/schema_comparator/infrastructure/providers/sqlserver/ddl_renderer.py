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


def _type_sql(attrs: ColumnAttributes) -> str:
    """The T-SQL type of `attrs`, without nullability."""
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
        return f"{clean_type}({size})"
    if attrs.numeric_precision is not None and data_type_lower in (
        "decimal",
        "numeric",
    ):
        if attrs.numeric_scale is not None:
            return f"{clean_type}({attrs.numeric_precision}, {attrs.numeric_scale})"
        return f"{clean_type}({attrs.numeric_precision})"
    return clean_type


def format_sql_column_definition(attrs: ColumnAttributes) -> str:
    """Format column attributes to their corresponding SQL Server (T-SQL) definition."""
    nullability = "NULL" if attrs.is_nullable else "NOT NULL"
    return f"{_type_sql(attrs)} {nullability}"


_STRING_TYPES = frozenset({"char", "varchar", "nchar", "nvarchar"})
_UNICODE_TYPES = frozenset({"nchar", "nvarchar"})
_NUMERIC_TYPES = frozenset(
    {
        "bit",
        "tinyint",
        "smallint",
        "int",
        "bigint",
        "decimal",
        "numeric",
        "float",
        "real",
        "money",
        "smallmoney",
    }
)
_TEMPORAL_TYPES = frozenset(
    {"date", "datetime", "datetime2", "smalldatetime", "datetimeoffset", "time"}
)
_BINARY_TYPES = frozenset({"binary", "varbinary"})
_FAMILIES = (_STRING_TYPES, _NUMERIC_TYPES, _TEMPORAL_TYPES, _BINARY_TYPES)
# Changes that never lose a value, beyond same-type widening.
_SAFE_WIDENINGS = frozenset(
    {
        ("tinyint", "smallint"),
        ("tinyint", "int"),
        ("tinyint", "bigint"),
        ("smallint", "int"),
        ("smallint", "bigint"),
        ("int", "bigint"),
        ("smallmoney", "money"),
        ("real", "float"),
        ("smalldatetime", "datetime"),
        ("date", "datetime2"),
        ("datetime", "datetime2"),
    }
)


def _base_type(attrs: ColumnAttributes) -> str:
    return re.sub(r"\s*\(.*\)", "", attrs.data_type).strip().lower()


def _family(base_type: str) -> frozenset | None:
    return next((f for f in _FAMILIES if base_type in f), None)


def _shorter(observed: ColumnAttributes, target: ColumnAttributes) -> bool:
    target_len = target.character_maximum_length
    observed_len = observed.character_maximum_length
    if target_len == -1:
        return False
    if observed_len == -1 or target_len is None or observed_len is None:
        return True
    return target_len < observed_len


def column_change_may_lose_data(
    observed: ColumnAttributes, target: ColumnAttributes
) -> bool:
    """Whether turning a column defined as `observed` into `target` can
    truncate, round or fail to convert a value: the script then counts the
    affected rows before changing anything."""
    old, new = _base_type(observed), _base_type(target)
    if old in _STRING_TYPES and new in _STRING_TYPES:
        if old in _UNICODE_TYPES and new not in _UNICODE_TYPES:
            return True
        return _shorter(observed, target)
    if old == new:
        if old in ("decimal", "numeric"):
            old_p, old_s = observed.numeric_precision or 18, observed.numeric_scale or 0
            new_p, new_s = target.numeric_precision or 18, target.numeric_scale or 0
            return new_s < old_s or new_p - new_s < old_p - old_s
        return False
    return (old, new) not in _SAFE_WIDENINGS


def _loss_is_checkable(observed: ColumnAttributes, target: ColumnAttributes) -> bool:
    """Whether the loss query can convert between both types; for other
    pairs the ALTER itself decides (and rolls back on error)."""
    old, new = _family(_base_type(observed)), _family(_base_type(target))
    if old is None or new is None:
        return False
    return old is new or _STRING_TYPES in (old, new)


def _fill_expression(attrs: ColumnAttributes, backfill_value: str | None) -> str | None:
    """What fills the rows left NULL by a change to NOT NULL: the value the
    user gave, else the column's default; None when there is neither."""
    if backfill_value is not None:
        return f"CONVERT({_type_sql(attrs)}, N'{_escape_literal(backfill_value)}')"
    if attrs.default_expression:
        expr = attrs.default_expression.strip()
        while expr.startswith("(") and expr.endswith(")") and len(expr) > 2:
            expr = expr[1:-1].strip()
        return expr or None
    return None


def _escape_ident(identifier: str) -> str:
    """Escape closing bracket for T-SQL bracketed identifiers."""
    return identifier.replace("]", "]]")


def _escape_literal(literal: str) -> str:
    """Escape single quote for T-SQL string literals."""
    return literal.replace("'", "''")


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
    # Drops foreign keys into the script-wide `@bdiff_fk` table.
    uses_fk_table: bool = False


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


def _dynamic(sql: str) -> str:
    """Run `sql` through sp_executesql: a statement naming a column that
    does not exist yet (or any more) would stop the whole batch compiling."""
    return f"EXEC sys.sp_executesql N'{_escape_literal(sql)}';"


def _count_rows(var: str, query: str) -> str:
    """Declare `var` and set it to the COUNT_BIG(*) of `query`'s FROM/WHERE."""
    sql = f"SELECT @n = COUNT_BIG(*) {query};"
    return (
        f"DECLARE {var} bigint;\n"
        f"EXEC sys.sp_executesql N'{_escape_literal(sql)}', "
        f"N'@n bigint OUTPUT', @n = {var} OUTPUT;"
    )


def _abort_if_rows(var: str, query: str, before: str, after: str) -> str:
    """Abort with `<before><count><after>` when `query` finds rows."""
    prefix = _escape_literal(before).replace("%", "%%")
    suffix = _escape_literal(after).replace("%", "%%")
    message = var.replace("@n_", "@msg_")
    return (
        f"{_count_rows(var, query)}\n"
        f"IF {var} > 0\n"
        "BEGIN\n"
        f"    DECLARE {message} nvarchar(2048) = N'{prefix}' + CAST({var} AS nvarchar(20)) + N'{suffix}';\n"
        f"    THROW 50003, {message}, 1;\n"
        "END"
    )


def _fill_value_check(label: str, attrs: ColumnAttributes, value: str) -> str:
    """Abort when the user's fill value does not convert to the column type
    (or, for text, would be cut or change on the way)."""
    type_sql = _type_sql(attrs)
    literal = f"N'{_escape_literal(value)}'"
    converted = f"TRY_CONVERT({type_sql}, {literal})"
    invalid = f"{converted} IS NULL"
    if _base_type(attrs) in _STRING_TYPES:
        invalid += (
            f" OR CAST(CAST({converted} AS nvarchar(4000)) AS varbinary(max))"
            f" <> CAST({literal} AS varbinary(max))"
        )
    return f"IF {invalid}\n    " + _throw(
        50004, f"{label}: el valor de relleno '{value}' no es valido para {type_sql}."
    )


def _lost_rows_query(
    table: str, col: str, observed: ColumnAttributes, target: ColumnAttributes
) -> str:
    """FROM/WHERE of the rows whose value would not survive the change: it
    does not convert, or converting it back does not give the same bytes.
    Text turned into another kind of type is only checked for conversion,
    since its spelling changes on the way back (dates, numbers)."""
    new_type, old_type = _type_sql(target), _type_sql(observed)
    converted = f"TRY_CONVERT({new_type}, [{col}])"
    lost = f"{converted} IS NULL"
    if not (
        _base_type(observed) in _STRING_TYPES
        and _base_type(target) not in _STRING_TYPES
    ):
        back = f"TRY_CONVERT({old_type}, {converted})"
        lost += (
            f" OR {back} IS NULL"
            f" OR CAST({back} AS varbinary(max)) <> CAST([{col}] AS varbinary(max))"
        )
    return f"FROM {table} WHERE [{col}] IS NOT NULL AND ({lost})"


def _data_checks(lines: list[str], skip: str) -> str:
    """Data checks run only when the step is not already applied."""
    if not lines:
        return ""
    body = "\n".join(_indent(line, 4) for line in lines)
    return f"\nIF {skip} = 0\nBEGIN\n{body}\nEND"


def _add_column_step(res, pos: _Position) -> _Step:
    table = _qualified(res.schema_name, res.table_name)
    column = _qualified(res.schema_name, res.table_name, res.column_name)
    label = pos.label(f"agregar la columna {column}")
    col_esc = _escape_ident(res.column_name)
    attrs = res.target_attributes
    col_def = format_sql_column_definition(attrs)
    fill = _fill_expression(attrs, res.backfill_value)
    data: list[str] = []
    if attrs.is_nullable:
        apply = f"ALTER TABLE {table} ADD [{col_esc}] {col_def};\n"
    elif fill is None:
        # Only an empty table can take a NOT NULL column with no value.
        data.append(
            _abort_if_rows(
                f"@n_{pos.number}_rows",
                f"FROM {table}",
                f"{label}: ",
                " fila(s) en la tabla y la columna nueva es NOT NULL sin DEFAULT;"
                " indica un valor de relleno en la TUI.",
            )
        )
        apply = f"ALTER TABLE {table} ADD [{col_esc}] {col_def};\n"
    else:
        if res.backfill_value is not None:
            data.append(
                "-- Relleno de NULL con el valor indicado en la TUI.\n"
                + _fill_value_check(label, attrs, res.backfill_value)
            )
        nullable_def = format_sql_column_definition(replace(attrs, is_nullable=True))
        apply = (
            "\n".join(
                _dynamic(sql)
                for sql in (
                    f"ALTER TABLE {table} ADD [{col_esc}] {nullable_def};",
                    f"UPDATE {table} SET [{col_esc}] = {fill} WHERE [{col_esc}] IS NULL;",
                    f"ALTER TABLE {table} ALTER COLUMN [{col_esc}] {col_def};",
                )
            )
            + "\n"
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
            "    "
            + _throw(50001, f"{label}: la tabla {table} no existe.")
            + _data_checks(data, pos.skip)
        ),
        apply=apply
        + f"PRINT N'Columna [{_escape_literal(col_esc)}] agregada con exito a {_escape_literal(table)}.';",
        verify=target,
    )


def _only_widens_text(
    observed: ColumnAttributes | None, target: ColumnAttributes
) -> bool:
    """A longer column of the same text type is a metadata change that
    indexes, defaults and checks allow; only foreign keys block it."""
    return (
        observed is not None
        and _base_type(observed) == _base_type(target)
        and _base_type(target) in _STRING_TYPES
        and observed.is_nullable == target.is_nullable
        and not _shorter(observed, target)
    )


def _list_sql(select: str) -> str:
    """Comma-separated values of a one-column SELECT (FOR XML PATH, which
    SQL Server 2016 has; STRING_AGG needs 2017)."""
    return f"STUFF(({select} FOR XML PATH(''), TYPE).value('.', 'nvarchar(max)'), 1, 2, N'')"


def _index_columns_sql(included: bool) -> str:
    if included:
        select = (
            "SELECT N', ' + QUOTENAME(c.name) FROM sys.index_columns ic "
            "JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id "
            "WHERE ic.object_id = i.object_id AND ic.index_id = i.index_id "
            "AND ic.is_included_column = 1 ORDER BY ic.index_column_id"
        )
    else:
        select = (
            "SELECT N', ' + QUOTENAME(c.name) + CASE WHEN ic.is_descending_key = 1 "
            "THEN N' DESC' ELSE N' ASC' END FROM sys.index_columns ic "
            "JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id "
            "WHERE ic.object_id = i.object_id AND ic.index_id = i.index_id "
            "AND ic.key_ordinal > 0 ORDER BY ic.key_ordinal"
        )
    return _list_sql(select)


def _fk_columns_sql(side: str) -> str:
    return _list_sql(
        "SELECT N', ' + QUOTENAME(COL_NAME(fkc."
        + side
        + "_object_id, fkc."
        + side
        + "_column_id)) FROM sys.foreign_key_columns fkc "
        "WHERE fkc.constraint_object_id = fk.object_id ORDER BY fkc.constraint_column_id"
    )


def _blockers_check(pos: _Position, label: str, widen_only: bool) -> str:
    """Abort naming the dependents BDIFF does not recreate."""
    n = pos.number
    obj, col = f"@obj_{n}", f"@col_{n}"
    sources = [
        "SELECT N', columna calculada ' + QUOTENAME(c.name) "
        "FROM sys.sql_expression_dependencies d JOIN sys.columns c "
        "ON c.object_id = d.referencing_id AND c.column_id = d.referencing_minor_id "
        f"WHERE d.referencing_id = {obj} AND d.referenced_id = {obj} "
        f"AND d.referenced_minor_id = {col} AND c.is_computed = 1",
        "SELECT N', objeto con SCHEMABINDING ' + QUOTENAME(OBJECT_SCHEMA_NAME(o.object_id)) "
        "+ N'.' + QUOTENAME(o.name) FROM sys.sql_expression_dependencies d "
        "JOIN sys.objects o ON o.object_id = d.referencing_id "
        f"WHERE d.referenced_id = {obj} AND d.referenced_minor_id = {col} "
        "AND d.is_schema_bound_reference = 1 AND o.type IN ('V', 'FN', 'IF', 'TF')",
    ]
    if not widen_only:
        on_column = (
            "EXISTS (SELECT 1 FROM sys.index_columns ic WHERE ic.object_id = i.object_id "
            f"AND ic.index_id = i.index_id AND ic.column_id = {col})"
        )
        sources += [
            "SELECT N', indice ' + QUOTENAME(i.name) + N' ' + i.type_desc COLLATE DATABASE_DEFAULT "
            f"FROM sys.indexes i WHERE i.object_id = {obj} AND i.type NOT IN (0, 1, 2) "
            f"AND {on_column}",
            "SELECT N', indice particionado ' + QUOTENAME(i.name) FROM sys.indexes i "
            "JOIN sys.partition_schemes ps ON ps.data_space_id = i.data_space_id "
            f"WHERE i.object_id = {obj} AND {on_column}",
            "SELECT N', indice full-text' FROM sys.fulltext_index_columns f "
            f"WHERE f.object_id = {obj} AND f.column_id = {col}",
        ]
    # FOR XML cannot apply to a UNION directly: wrap it in a derived table.
    union = (
        "SELECT x.what AS [text()] FROM ("
        + " UNION ALL ".join(sources)
        + ") AS x(what)"
    )
    prefix = _escape_literal(
        f"{label}: la columna tiene dependencias que BDIFF no recrea: "
    ).replace("%", "%%")
    return (
        f"DECLARE @blockers_{n} nvarchar(max) = {_list_sql(union)};\n"
        f"IF @blockers_{n} IS NOT NULL\n"
        "BEGIN\n"
        f"    DECLARE @blockers_msg_{n} nvarchar(2048) = LEFT(N'{prefix}' + REPLACE(@blockers_{n}, N'%', N'%%')"
        " + N'; ajustalas a mano antes de aplicar.', 2048);\n"
        f"    THROW 50005, @blockers_msg_{n}, 1;\n"
        "END"
    )


def _run_each(cursor: str, var: str, select: str) -> str:
    """Execute, in order, every statement `select` returns."""
    return (
        f"DECLARE {cursor} CURSOR LOCAL FAST_FORWARD FOR {select};\n"
        f"OPEN {cursor};\n"
        f"FETCH NEXT FROM {cursor} INTO {var};\n"
        "WHILE @@FETCH_STATUS = 0\n"
        "BEGIN\n"
        f"    EXEC sys.sp_executesql {var};\n"
        f"    FETCH NEXT FROM {cursor} INTO {var};\n"
        "END\n"
        f"CLOSE {cursor};\n"
        f"DEALLOCATE {cursor};"
    )


# Dependents of a column, in drop order (recreated in reverse): statistics
# and nonclustered indexes, then the clustered one, then DEFAULT and CHECK.
_KIND_NONCLUSTERED, _KIND_CLUSTERED, _KIND_CONSTRAINT = 1, 2, 3


def _collect_dependents(n: int, widen_only: bool) -> str:
    """Fill `@deps_<n>` with the drop and recreate statements of the
    column's indexes, statistics, DEFAULT and CHECK, and `@bdiff_fk` with
    its foreign keys (recreated once every step has run)."""
    obj, col, tbl, deps = f"@obj_{n}", f"@col_{n}", f"@tbl_{n}", f"@deps_{n}"
    on_column = (
        "EXISTS (SELECT 1 FROM sys.index_columns ic WHERE ic.object_id = i.object_id "
        f"AND ic.index_id = i.index_id AND ic.column_id = {col})"
    )
    is_constraint = "(i.is_primary_key = 1 OR i.is_unique_constraint = 1)"
    kind_word = "CASE WHEN i.type = 1 THEN N'CLUSTERED' ELSE N'NONCLUSTERED' END"
    index_sql = (
        f"INSERT {deps} (kind, name, drop_sql, create_sql)\n"
        f"SELECT CASE WHEN i.type = 1 THEN {_KIND_CLUSTERED} ELSE {_KIND_NONCLUSTERED} END, i.name,\n"
        f"    CASE WHEN {is_constraint}\n"
        f"        THEN N'ALTER TABLE ' + {tbl} + N' DROP CONSTRAINT ' + QUOTENAME(i.name)\n"
        f"        ELSE N'DROP INDEX ' + QUOTENAME(i.name) + N' ON ' + {tbl} END,\n"
        f"    CASE WHEN {is_constraint}\n"
        f"        THEN N'ALTER TABLE ' + {tbl} + N' ADD CONSTRAINT ' + QUOTENAME(i.name)\n"
        "            + CASE WHEN i.is_primary_key = 1 THEN N' PRIMARY KEY ' ELSE N' UNIQUE ' END + "
        f"{kind_word}\n"
        "        ELSE N'CREATE ' + CASE WHEN i.is_unique = 1 THEN N'UNIQUE ' ELSE N'' END + "
        f"{kind_word}\n"
        f"            + N' INDEX ' + QUOTENAME(i.name) + N' ON ' + {tbl} END\n"
        f"    + N' (' + {_index_columns_sql(included=False)} + N')'\n"
        f"    + ISNULL(N' INCLUDE (' + {_index_columns_sql(included=True)} + N')', N'')\n"
        "    + CASE WHEN i.has_filter = 1 THEN N' WHERE ' + i.filter_definition ELSE N'' END\n"
        "    + N' WITH (PAD_INDEX = ' + CASE WHEN i.is_padded = 1 THEN N'ON' ELSE N'OFF' END\n"
        "    + CASE WHEN i.fill_factor > 0 THEN N', FILLFACTOR = ' + CAST(i.fill_factor AS nvarchar(3)) ELSE N'' END\n"
        "    + CASE WHEN i.ignore_dup_key = 1 THEN N', IGNORE_DUP_KEY = ON' ELSE N'' END\n"
        "    + N', ALLOW_ROW_LOCKS = ' + CASE WHEN i.allow_row_locks = 1 THEN N'ON' ELSE N'OFF' END\n"
        "    + N', ALLOW_PAGE_LOCKS = ' + CASE WHEN i.allow_page_locks = 1 THEN N'ON' ELSE N'OFF' END\n"
        "    + ISNULL((SELECT TOP (1) N', DATA_COMPRESSION = ' + p.data_compression_desc COLLATE DATABASE_DEFAULT\n"
        "        FROM sys.partitions p WHERE p.object_id = i.object_id AND p.index_id = i.index_id\n"
        "        AND p.data_compression > 0), N'')\n"
        "    + N') ON ' + QUOTENAME(ds.name)\n"
        "    + CASE WHEN i.is_disabled = 1\n"
        f"        THEN N'; ALTER INDEX ' + QUOTENAME(i.name) + N' ON ' + {tbl} + N' DISABLE' ELSE N'' END\n"
        "FROM sys.indexes i JOIN sys.data_spaces ds ON ds.data_space_id = i.data_space_id\n"
        f"WHERE i.object_id = {obj} AND i.type IN (1, 2) AND i.is_hypothetical = 0 AND {on_column};\n"
    )
    stats_columns = _list_sql(
        "SELECT N', ' + QUOTENAME(COL_NAME(sc.object_id, sc.column_id)) FROM sys.stats_columns sc "
        "WHERE sc.object_id = s.object_id AND sc.stats_id = s.stats_id ORDER BY sc.stats_column_id"
    )
    stats_sql = (
        f"INSERT {deps} (kind, name, drop_sql, create_sql)\n"
        f"SELECT {_KIND_NONCLUSTERED}, s.name, N'DROP STATISTICS ' + {tbl} + N'.' + QUOTENAME(s.name),\n"
        "    CASE WHEN s.user_created = 1\n"
        f"        THEN N'CREATE STATISTICS ' + QUOTENAME(s.name) + N' ON ' + {tbl} + N' (' + {stats_columns} + N')'\n"
        "            + CASE WHEN s.has_filter = 1 THEN N' WHERE ' + s.filter_definition ELSE N'' END END\n"
        "FROM sys.stats s\n"
        f"WHERE s.object_id = {obj} AND (s.user_created = 1 OR s.auto_created = 1)\n"
        "  AND EXISTS (SELECT 1 FROM sys.stats_columns sc WHERE sc.object_id = s.object_id\n"
        f"      AND sc.stats_id = s.stats_id AND sc.column_id = {col});\n"
    )
    constraint_sql = (
        f"INSERT {deps} (kind, name, drop_sql, create_sql)\n"
        f"SELECT {_KIND_CONSTRAINT}, dc.name, N'ALTER TABLE ' + {tbl} + N' DROP CONSTRAINT ' + QUOTENAME(dc.name),\n"
        f"    N'ALTER TABLE ' + {tbl} + N' ADD CONSTRAINT ' + QUOTENAME(dc.name) + N' DEFAULT ' + dc.definition\n"
        f"    + N' FOR ' + QUOTENAME(COL_NAME({obj}, {col}))\n"
        f"FROM sys.default_constraints dc WHERE dc.parent_object_id = {obj} AND dc.parent_column_id = {col};\n"
        f"INSERT {deps} (kind, name, drop_sql, create_sql)\n"
        f"SELECT {_KIND_CONSTRAINT}, cc.name, N'ALTER TABLE ' + {tbl} + N' DROP CONSTRAINT ' + QUOTENAME(cc.name),\n"
        f"    N'ALTER TABLE ' + {tbl} + CASE WHEN cc.is_not_trusted = 1 THEN N' WITH NOCHECK' ELSE N' WITH CHECK' END\n"
        "    + N' ADD CONSTRAINT ' + QUOTENAME(cc.name) + N' CHECK '\n"
        "    + CASE WHEN cc.is_not_for_replication = 1 THEN N'NOT FOR REPLICATION ' ELSE N'' END + cc.definition\n"
        "    + CASE WHEN cc.is_disabled = 1\n"
        f"        THEN N'; ALTER TABLE ' + {tbl} + N' NOCHECK CONSTRAINT ' + QUOTENAME(cc.name) ELSE N'' END\n"
        f"FROM sys.check_constraints cc WHERE cc.parent_object_id = {obj}\n"
        f"  AND (cc.parent_column_id = {col} OR EXISTS (SELECT 1 FROM sys.sql_expression_dependencies d\n"
        f"      WHERE d.referencing_id = cc.object_id AND d.referenced_id = {obj} AND d.referenced_minor_id = {col}));\n"
    )
    qualified = "QUOTENAME(OBJECT_SCHEMA_NAME(fk.{0}_object_id)) + N'.' + QUOTENAME(OBJECT_NAME(fk.{0}_object_id))"
    parent, referenced = qualified.format("parent"), qualified.format("referenced")
    fk_sql = (
        "INSERT @bdiff_fk (fk_id, step, name, drop_sql, create_sql)\n"
        f"SELECT fk.object_id, {n}, fk.name,\n"
        f"    N'ALTER TABLE ' + {parent} + N' DROP CONSTRAINT ' + QUOTENAME(fk.name),\n"
        f"    N'ALTER TABLE ' + {parent}\n"
        "    + CASE WHEN fk.is_not_trusted = 1 THEN N' WITH NOCHECK' ELSE N' WITH CHECK' END\n"
        f"    + N' ADD CONSTRAINT ' + QUOTENAME(fk.name) + N' FOREIGN KEY (' + {_fk_columns_sql('parent')} + N')'\n"
        f"    + N' REFERENCES ' + {referenced} + N' (' + {_fk_columns_sql('referenced')} + N')'\n"
        "    + N' ON DELETE ' + REPLACE(fk.delete_referential_action_desc COLLATE DATABASE_DEFAULT, N'_', N' ')\n"
        "    + N' ON UPDATE ' + REPLACE(fk.update_referential_action_desc COLLATE DATABASE_DEFAULT, N'_', N' ')\n"
        "    + CASE WHEN fk.is_not_for_replication = 1 THEN N' NOT FOR REPLICATION' ELSE N'' END\n"
        "    + CASE WHEN fk.is_disabled = 1\n"
        f"        THEN N'; ALTER TABLE ' + {parent} + N' NOCHECK CONSTRAINT ' + QUOTENAME(fk.name) ELSE N'' END\n"
        "FROM sys.foreign_keys fk\n"
        "WHERE fk.object_id NOT IN (SELECT fk_id FROM @bdiff_fk)\n"
        f"  AND ((fk.parent_object_id = {obj} AND EXISTS (SELECT 1 FROM sys.foreign_key_columns fkc\n"
        f"          WHERE fkc.constraint_object_id = fk.object_id AND fkc.parent_column_id = {col}))\n"
        f"    OR (fk.referenced_object_id = {obj} AND EXISTS (SELECT 1 FROM sys.foreign_key_columns fkc\n"
        f"          WHERE fkc.constraint_object_id = fk.object_id AND fkc.referenced_column_id = {col})));\n"
    )
    sql = (
        f"DECLARE {deps} TABLE (seq int IDENTITY(1, 1), kind tinyint NOT NULL, name sysname NOT NULL,\n"
        "    drop_sql nvarchar(max) NOT NULL, create_sql nvarchar(max) NULL);\n"
        f"DECLARE @dep_sql_{n} nvarchar(max);\n" + fk_sql
    )
    if not widen_only:
        sql += index_sql + stats_sql + constraint_sql
    return sql


def _drop_dependents(n: int, label: str) -> str:
    warning = _escape_literal(
        f"{label}: aviso: se recrea el indice clustered o la PK; esto reconstruye la tabla completa."
    )
    return (
        f"IF EXISTS (SELECT 1 FROM @deps_{n} WHERE kind = {_KIND_CLUSTERED})\n"
        f"    PRINT N'{warning}';\n"
        + _run_each(
            f"bdiff_fk_drop_{n}",
            f"@dep_sql_{n}",
            f"SELECT drop_sql FROM @bdiff_fk WHERE step = {n} ORDER BY fk_id",
        )
        + "\n"
        + _run_each(
            f"bdiff_dep_drop_{n}",
            f"@dep_sql_{n}",
            f"SELECT drop_sql FROM @deps_{n} ORDER BY kind, seq",
        )
    )


def _recreate_dependents(n: int) -> str:
    return _run_each(
        f"bdiff_dep_create_{n}",
        f"@dep_sql_{n}",
        f"SELECT create_sql FROM @deps_{n} WHERE create_sql IS NOT NULL ORDER BY kind DESC, seq",
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
    n = pos.number
    widen_only = _only_widens_text(observed, attrs)
    check = (
        f"DECLARE @obj_{n} int = OBJECT_ID(N'{table_lit}');\n"
        f"DECLARE @col_{n} int = COLUMNPROPERTY(@obj_{n}, N'{_escape_literal(res.column_name)}', 'ColumnId');\n"
        f"DECLARE @tbl_{n} nvarchar(400) = N'{table_lit}';\n"
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

    data: list[str] = [_blockers_check(pos, label, widen_only)]
    fill = None
    if not attrs.is_nullable and (observed is None or observed.is_nullable):
        fill = _fill_expression(attrs, res.backfill_value)
        if fill is None:
            data.append(
                _abort_if_rows(
                    f"@n_{pos.number}_nulls",
                    f"FROM {table} WHERE [{col_esc}] IS NULL",
                    f"{label}: ",
                    " fila(s) con NULL y la definicion objetivo es NOT NULL sin"
                    " DEFAULT; indica un valor de relleno en la TUI o corrige los"
                    " datos.",
                )
            )
        elif res.backfill_value is not None:
            data.append(
                "-- Relleno de NULL con el valor indicado en la TUI.\n"
                + _fill_value_check(label, attrs, res.backfill_value)
            )
    if (
        observed is not None
        and column_change_may_lose_data(observed, attrs)
        and _loss_is_checkable(observed, attrs)
    ):
        query = _lost_rows_query(table, col_esc, observed, attrs)
        var = f"@n_{pos.number}_lost"
        if res.accept_data_loss:
            data.append(
                "-- Perdida de datos aceptada explicitamente en la TUI para esta columna.\n"
                f"{_count_rows(var, query)}\n"
                f"IF {var} > 0\n"
                f"    PRINT N'{_escape_literal(label)}: perdida de datos aceptada en '"
                f" + CAST({var} AS nvarchar(20)) + N' fila(s).';"
            )
        else:
            data.append(
                _abort_if_rows(
                    var,
                    query,
                    f"{label}: ",
                    f" fila(s) perderian datos al convertir a {_type_sql(attrs)}"
                    " (truncamiento, redondeo o conversion); corrige los datos o"
                    " acepta la perdida en la TUI.",
                )
            )

    # Indexes, statistics and constraints on the column block most ALTER
    # COLUMN changes: they are dropped and recreated around it, and the
    # foreign keys once every step has run.
    apply = (
        "-- Si la columna forma parte del indice clustered o de la PK, recrearlo\n"
        "-- reconstruye la tabla completa.\n"
        + _collect_dependents(n, widen_only)
        + _drop_dependents(n, label)
        + "\n"
    )
    if fill is not None:
        update = f"UPDATE {table} SET [{col_esc}] = {fill} WHERE [{col_esc}] IS NULL;"
        apply += (
            f"{_dynamic(update)}\n"
            f"PRINT N'Valores NULL en {table_lit}.[{col_print}] actualizados pre-ALTER.';\n"
        )
    apply += (
        f"ALTER TABLE {table} ALTER COLUMN [{col_esc}] {format_sql_column_definition(attrs)};\n"
        f"{_recreate_dependents(n)}\n"
        f"PRINT N'Columna [{col_print}] de {table_lit} modificada con exito.';"
    )
    return _Step(
        label=label,
        check=check + _data_checks(data, pos.skip),
        apply=apply,
        verify=target,
        uses_fk_table=True,
    )


def _indent(text: str, spaces: int) -> str:
    pad = " " * spaces
    return "\n".join(pad + line if line else line for line in text.splitlines())


def _render_steps(steps: list[_Step]) -> list[str]:
    if not steps:
        return ["    PRINT N'No se requieren cambios para este perfil.';"]
    flags = ", ".join(f"@skip_{n} bit = 0" for n in range(1, len(steps) + 1))
    uses_fk_table = any(step.uses_fk_table for step in steps)
    lines = [f"    DECLARE {flags};"]
    if uses_fk_table:
        lines += [
            "    -- Claves foraneas eliminadas por los pasos; se recrean al final.",
            "    DECLARE @bdiff_fk TABLE (fk_id int PRIMARY KEY, step int NOT NULL, name sysname NOT NULL,",
            "        drop_sql nvarchar(max) NOT NULL, create_sql nvarchar(max) NOT NULL);",
            "    DECLARE @bdiff_fk_sql nvarchar(max);",
        ]
    lines += [
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
    if uses_fk_table:
        lines += [
            "",
            "    -- Claves foraneas recreadas tras todos los cambios.",
            _indent(
                _run_each(
                    "bdiff_fk_create",
                    "@bdiff_fk_sql",
                    "SELECT create_sql FROM @bdiff_fk ORDER BY fk_id",
                ),
                4,
            ),
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
