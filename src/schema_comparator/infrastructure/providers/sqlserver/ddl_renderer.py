"""T-SQL DDL script generator for SQL Server microservice schema consolidation."""

import datetime
import hashlib
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
    if attrs.datetime_precision is not None and data_type_lower in _FRACTIONAL_TYPES:
        return f"{clean_type}({attrs.datetime_precision})"
    return clean_type


def _column_parts(attrs: ColumnAttributes, *, identity: bool) -> str:
    parts = [_type_sql(attrs)]
    if attrs.collation:
        parts.append(f"COLLATE {attrs.collation}")
    if identity and attrs.is_identity:
        # BDIFF does not extract seed and increment.
        parts.append("IDENTITY(1, 1)")
    parts.append("NULL" if attrs.is_nullable else "NOT NULL")
    return " ".join(parts)


def format_sql_column_definition(attrs: ColumnAttributes) -> str:
    """Type, explicit collation and nullability: the part of a column
    definition ALTER COLUMN accepts (IDENTITY and DEFAULT are not)."""
    return _column_parts(attrs, identity=False)


def _default_name(table: str, column: str) -> str:
    return f"DF_{table}_{column}"[:128]


def _new_column_sql(table: str, column: str, attrs: ColumnAttributes) -> str:
    """A column definition for CREATE TABLE or ADD: with IDENTITY and a
    named DEFAULT."""
    sql = _column_parts(attrs, identity=True)
    if attrs.default_expression:
        name = _escape_ident(_default_name(table, column))
        sql += f" CONSTRAINT [{name}] DEFAULT {attrs.default_expression}"
    return sql


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
# Types whose fractional-second digits are part of the definition.
_FRACTIONAL_TYPES = frozenset({"datetime2", "time", "datetimeoffset"})
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
        if old in _FRACTIONAL_TYPES:
            # Without a precision the type takes 7 digits.
            old_digits = (
                7
                if observed.datetime_precision is None
                else observed.datetime_precision
            )
            new_digits = (
                7 if target.datetime_precision is None else target.datetime_precision
            )
            return new_digits < old_digits
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


# Data copied before every DROP, and the journal of the constraints and
# indexes the script drops with their definitions, to undo it.
BACKUP_SCHEMA = "bdiff_respaldo"


def _bounded(name: str) -> str:
    """`name` within SQL Server's 128 characters, kept unique by a hash."""
    if len(name) <= 128:
        return name
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    return f"{name[:119]}_{digest}"


def backup_table_name(
    timestamp: datetime.datetime, table: str, column: str | None = None
) -> str:
    stamp = timestamp.strftime("%Y%m%d_%H%M%S")
    suffix = f"_{column}" if column is not None else ""
    return _bounded(f"bdiff_bak_{stamp}_{table}{suffix}")


def journal_table_name(timestamp: datetime.datetime) -> str:
    return f"bdiff_diario_{timestamp.strftime('%Y%m%d_%H%M%S')}"


def _backup_qualified(name: str) -> str:
    return f"[{BACKUP_SCHEMA}].[{_escape_ident(name)}]"


def _ensure_backup_storage(journal: str) -> str:
    """Create the backup schema and the journal when missing (each via
    sp_executesql: CREATE SCHEMA must be alone in its batch)."""
    create_journal = (
        f"CREATE TABLE {journal} (seq int IDENTITY(1, 1) PRIMARY KEY, paso int NOT NULL,"
        " objeto sysname NOT NULL, sql nvarchar(max) NOT NULL);"
    )
    return (
        f"IF SCHEMA_ID(N'{BACKUP_SCHEMA}') IS NULL\n"
        f"    EXEC sys.sp_executesql N'CREATE SCHEMA [{BACKUP_SCHEMA}];';\n"
        f"IF OBJECT_ID(N'{_escape_literal(journal)}', N'U') IS NULL\n"
        f"    {_dynamic(create_journal)}\n"
    )


def _backup_must_not_exist(label: str, backup: str) -> str:
    return (
        f"IF OBJECT_ID(N'{_escape_literal(backup)}', N'U') IS NOT NULL\n    "
        + _throw(
            50007,
            f"{label}: ya existe el respaldo {backup}; renombralo o eliminalo antes de aplicar.",
        )
    )


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
    if data_type in _FRACTIONAL_TYPES and attrs.datetime_precision is not None:
        conditions.append(f"DATETIME_PRECISION = {int(attrs.datetime_precision)}")
    if data_type in _STRING_TYPES:
        # No explicit collation means the database's, as the extraction reads it.
        conditions.append(
            f"COLLATION_NAME = N'{_escape_literal(attrs.collation)}'"
            if attrs.collation
            else "COLLATION_NAME = CONVERT(nvarchar(128), DATABASEPROPERTYEX(DB_NAME(), 'Collation'))"
        )
    conditions.append(
        f"COLUMN_DEFAULT = N'{_escape_literal(attrs.default_expression)}'"
        if attrs.default_expression
        else "COLUMN_DEFAULT IS NULL"
    )
    conditions.append(
        "COLUMNPROPERTY(OBJECT_ID(QUOTENAME(TABLE_SCHEMA) + N'.' + QUOTENAME(TABLE_NAME)),"
        f" COLUMN_NAME, 'IsIdentity') = {1 if attrs.is_identity else 0}"
    )
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
        f"    [{_escape_ident(c.name)}] "
        f"{_new_column_sql(tres.table_name, c.name, c.attributes)}"
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


def _drop_table_step(tdel, pos: _Position, ts: datetime.datetime) -> _Step:
    table = _qualified(tdel.schema_name, tdel.table_name)
    table_lit = _escape_literal(table)
    label = pos.label(f"eliminar la tabla {table}")
    exists = _table_exists(tdel.schema_name, tdel.table_name)
    backup = _backup_qualified(backup_table_name(ts, tdel.table_name))
    journal = _backup_qualified(journal_table_name(ts))
    n = pos.number
    return _Step(
        label=label,
        check=(
            f"IF NOT ({exists})\n    SET {pos.skip} = 1;"
            + _data_checks([_backup_must_not_exist(label, backup)], pos.skip)
        ),
        apply=(
            _ensure_backup_storage(journal)
            + f"{_dynamic(f'SELECT * INTO {backup} FROM {table};')}\n"
            + f"PRINT N'Datos respaldados en {_escape_literal(backup)}.';\n"
            # Keys of other tables pointing at it: journaled, then dropped.
            + f"DECLARE @fk_{n} TABLE (name sysname, drop_sql nvarchar(max), create_sql nvarchar(max));\n"
            + f"DECLARE @fk_sql_{n} nvarchar(max);\n"
            + f"INSERT @fk_{n} (name, drop_sql, create_sql)\n"
            + f"SELECT fk.name, {_FK_DROP_SQL},\n    {_fk_create_sql()}\n"
            + f"FROM sys.foreign_keys fk WHERE fk.referenced_object_id = OBJECT_ID(N'{table_lit}');\n"
            + f"INSERT {journal} (paso, objeto, sql) SELECT {n}, name, create_sql FROM @fk_{n};\n"
            + _run_each(
                f"bdiff_fk_drop_{n}", f"@fk_sql_{n}", f"SELECT drop_sql FROM @fk_{n}"
            )
            + f"\nDROP TABLE {table};\n"
            + f"PRINT N'Tabla {table_lit} eliminada con exito.';"
        ),
        verify=f"NOT ({exists})",
    )


def _drop_column_step(cdel, pos: _Position, ts: datetime.datetime) -> _Step:
    table = _qualified(cdel.schema_name, cdel.table_name)
    table_lit = _escape_literal(table)
    col_esc = _escape_ident(cdel.column_name)
    col_lit = _escape_literal(cdel.column_name)
    label = pos.label(
        f"eliminar la columna {_qualified(cdel.schema_name, cdel.table_name, cdel.column_name)}"
    )
    exists = _column_exists(cdel.schema_name, cdel.table_name, cdel.column_name)
    backup = _backup_qualified(backup_table_name(ts, cdel.table_name, cdel.column_name))
    backup_lit = _escape_literal(backup)
    journal = _backup_qualified(journal_table_name(ts))
    n = pos.number
    pk_columns = _list_sql(
        "SELECT N', ' + QUOTENAME(c.name) FROM sys.indexes i "
        "JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id "
        "JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id "
        f"WHERE i.object_id = @obj_{n} AND i.is_primary_key = 1 ORDER BY ic.key_ordinal"
    )
    no_key = _escape_literal(
        f"{label}: aviso: la tabla no tiene una PK sin esta columna (sin PK); se respalda"
        " completa y al deshacer no se podran emparejar las filas."
    )
    return _Step(
        label=label,
        check=(
            f"DECLARE @obj_{n} int = OBJECT_ID(N'{table_lit}');\n"
            f"DECLARE @col_{n} int = COLUMNPROPERTY(@obj_{n}, N'{col_lit}', 'ColumnId');\n"
            f"DECLARE @tbl_{n} nvarchar(400) = N'{table_lit}';\n"
            f"IF NOT {exists}\n    SET {pos.skip} = 1;"
            + _data_checks(
                [
                    _blockers_check(pos, label, widen_only=False),
                    _backup_must_not_exist(label, backup),
                ],
                pos.skip,
            )
        ),
        apply=(
            _ensure_backup_storage(journal)
            # The primary key and the column, so undoing can put each value
            # back in its row; the whole table when the key is missing or
            # includes the column.
            + f"DECLARE @pk_{n} nvarchar(max) = CASE WHEN EXISTS (SELECT 1 FROM sys.indexes i\n"
            + "    JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id\n"
            + f"    WHERE i.object_id = @obj_{n} AND i.is_primary_key = 1 AND ic.column_id = @col_{n})\n"
            + f"    THEN NULL ELSE {pk_columns} END;\n"
            + f"DECLARE @bak_sql_{n} nvarchar(max) = N'SELECT * INTO {backup_lit} FROM ' + @tbl_{n};\n"
            + f"IF @pk_{n} IS NULL\n"
            + f"    PRINT N'{no_key}';\n"
            + "ELSE\n"
            + f"    SET @bak_sql_{n} = N'SELECT ' + @pk_{n} + N', [{_escape_literal(col_esc)}] INTO {backup_lit} FROM ' + @tbl_{n};\n"
            + f"EXEC sys.sp_executesql @bak_sql_{n};\n"
            + f"PRINT N'Datos respaldados en {_escape_literal(backup)}.';\n"
            + _collect_dependents(
                n, widen_only=False, keep_default=True, recreate_fks=False
            )
            + f"INSERT {journal} (paso, objeto, sql)\n"
            + f"SELECT {n}, name, create_sql FROM @deps_{n} WHERE create_sql IS NOT NULL\n"
            + f"UNION ALL SELECT {n}, name, create_sql FROM @bdiff_fk WHERE step = {n};\n"
            + _drop_dependents(n, label)
            + f"\nALTER TABLE {table} DROP COLUMN [{col_esc}];\n"
            + f"PRINT N'Columna [{_escape_literal(col_esc)}] eliminada con exito de {table_lit}.';"
        ),
        verify=f"NOT {exists}",
        uses_fk_table=True,
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
    new_def = _new_column_sql(res.table_name, res.column_name, attrs)
    add = f"ALTER TABLE {table} ADD [{col_esc}] {new_def};\n"
    data: list[str] = []
    if attrs.is_nullable or attrs.default_expression or attrs.is_identity:
        # A NOT NULL column with a DEFAULT or IDENTITY fills existing rows.
        apply = add
    elif res.backfill_value is None:
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
        apply = add
    else:
        data.append(
            "-- Relleno de NULL con el valor indicado en la TUI.\n"
            + _fill_value_check(label, attrs, res.backfill_value)
        )
        fill = _fill_expression(attrs, res.backfill_value)
        nullable_def = _new_column_sql(
            res.table_name, res.column_name, replace(attrs, is_nullable=True)
        )
        apply = (
            "\n".join(
                _dynamic(sql)
                for sql in (
                    f"ALTER TABLE {table} ADD [{col_esc}] {nullable_def};",
                    f"UPDATE {table} SET [{col_esc}] = {fill} WHERE [{col_esc}] IS NULL;",
                    f"ALTER TABLE {table} ALTER COLUMN [{col_esc}] "
                    f"{format_sql_column_definition(attrs)};",
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
        and observed.collation == target.collation
        and not _shorter(observed, target)
    )


def _definition(attrs: ColumnAttributes) -> ColumnAttributes:
    """What ALTER COLUMN changes: everything but the DEFAULT and IDENTITY."""
    return replace(attrs, default_expression=None, is_identity=False)


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


_FK_PARENT = "QUOTENAME(OBJECT_SCHEMA_NAME(fk.parent_object_id)) + N'.' + QUOTENAME(OBJECT_NAME(fk.parent_object_id))"
_FK_DROP_SQL = (
    f"N'ALTER TABLE ' + {_FK_PARENT} + N' DROP CONSTRAINT ' + QUOTENAME(fk.name)"
)


def _fk_create_sql() -> str:
    """T-SQL expression, over `sys.foreign_keys fk`, that recreates the key
    with its columns, actions and trusted or disabled state."""
    referenced = (
        "QUOTENAME(OBJECT_SCHEMA_NAME(fk.referenced_object_id)) + N'.' "
        "+ QUOTENAME(OBJECT_NAME(fk.referenced_object_id))"
    )
    return (
        f"N'ALTER TABLE ' + {_FK_PARENT}\n"
        "    + CASE WHEN fk.is_not_trusted = 1 THEN N' WITH NOCHECK' ELSE N' WITH CHECK' END\n"
        f"    + N' ADD CONSTRAINT ' + QUOTENAME(fk.name) + N' FOREIGN KEY (' + {_fk_columns_sql('parent')} + N')'\n"
        f"    + N' REFERENCES ' + {referenced} + N' (' + {_fk_columns_sql('referenced')} + N')'\n"
        "    + N' ON DELETE ' + REPLACE(fk.delete_referential_action_desc COLLATE DATABASE_DEFAULT, N'_', N' ')\n"
        "    + N' ON UPDATE ' + REPLACE(fk.update_referential_action_desc COLLATE DATABASE_DEFAULT, N'_', N' ')\n"
        "    + CASE WHEN fk.is_not_for_replication = 1 THEN N' NOT FOR REPLICATION' ELSE N'' END\n"
        "    + CASE WHEN fk.is_disabled = 1\n"
        f"        THEN N'; ALTER TABLE ' + {_FK_PARENT} + N' NOCHECK CONSTRAINT ' + QUOTENAME(fk.name) ELSE N'' END"
    )


def _collect_dependents(
    n: int, widen_only: bool, keep_default: bool, recreate_fks: bool = True
) -> str:
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
    default_sql = (
        f"INSERT {deps} (kind, name, drop_sql, create_sql)\n"
        f"SELECT {_KIND_CONSTRAINT}, dc.name, N'ALTER TABLE ' + {tbl} + N' DROP CONSTRAINT ' + QUOTENAME(dc.name),\n"
        f"    N'ALTER TABLE ' + {tbl} + N' ADD CONSTRAINT ' + QUOTENAME(dc.name) + N' DEFAULT ' + dc.definition\n"
        f"    + N' FOR ' + QUOTENAME(COL_NAME({obj}, {col}))\n"
        f"FROM sys.default_constraints dc WHERE dc.parent_object_id = {obj} AND dc.parent_column_id = {col};\n"
    )
    check_sql = (
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
    fk_sql = (
        "INSERT @bdiff_fk (fk_id, step, recreate, name, drop_sql, create_sql)\n"
        f"SELECT fk.object_id, {n}, {1 if recreate_fks else 0}, fk.name,\n"
        f"    {_FK_DROP_SQL},\n"
        f"    {_fk_create_sql()}\n"
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
        sql += index_sql + stats_sql + check_sql
        # A changing DEFAULT is dropped and added by the step itself.
        if keep_default:
            sql += default_sql
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
    alter = observed is None or _definition(observed) != _definition(attrs)
    default_changes = (
        observed is None or observed.default_expression != attrs.default_expression
    )
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

    data: list[str] = [
        f"IF COLUMNPROPERTY(@obj_{n}, N'{_escape_literal(res.column_name)}', 'IsIdentity')"
        f" <> {1 if attrs.is_identity else 0}\n    "
        + _throw(
            50006,
            f"{label}: cambiar IDENTITY exige reconstruir la tabla y BDIFF no lo hace;"
            " aplicalo a mano.",
        )
    ]
    if alter:
        data.append(_blockers_check(pos, label, widen_only))
    fill = None
    if alter and not attrs.is_nullable and (observed is None or observed.is_nullable):
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
        alter
        and observed is not None
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
    apply = ""
    if alter:
        apply += (
            "-- Si la columna forma parte del indice clustered o de la PK, recrearlo\n"
            "-- reconstruye la tabla completa.\n"
            + _collect_dependents(n, widen_only, keep_default=not default_changes)
            + _drop_dependents(n, label)
            + "\n"
        )
    if default_changes:
        # The DEFAULT changes: drop the current one, add the target's under
        # the same name (or DF_<table>_<column> when there was none).
        apply += (
            f"DECLARE @df_{n} sysname = (SELECT name FROM sys.default_constraints\n"
            f"    WHERE parent_object_id = @obj_{n} AND parent_column_id = @col_{n});\n"
            f"DECLARE @df_sql_{n} nvarchar(max);\n"
            f"IF @df_{n} IS NOT NULL\n"
            "BEGIN\n"
            f"    SET @df_sql_{n} = N'ALTER TABLE ' + @tbl_{n} + N' DROP CONSTRAINT ' + QUOTENAME(@df_{n});\n"
            f"    EXEC sys.sp_executesql @df_sql_{n};\n"
            "END\n"
        )
    if alter:
        if fill is not None:
            update = (
                f"UPDATE {table} SET [{col_esc}] = {fill} WHERE [{col_esc}] IS NULL;"
            )
            apply += (
                f"{_dynamic(update)}\n"
                f"PRINT N'Valores NULL en {table_lit}.[{col_print}] actualizados pre-ALTER.';\n"
            )
        apply += (
            f"ALTER TABLE {table} ALTER COLUMN [{col_esc}] {format_sql_column_definition(attrs)};\n"
            f"{_recreate_dependents(n)}\n"
        )
    if default_changes and attrs.default_expression:
        fallback = _escape_literal(_default_name(res.table_name, res.column_name))
        expression = _escape_literal(attrs.default_expression)
        apply += (
            f"SET @df_sql_{n} = N'ALTER TABLE ' + @tbl_{n} + N' ADD CONSTRAINT '"
            f" + QUOTENAME(ISNULL(@df_{n}, N'{fallback}')) + N' DEFAULT {expression}'"
            f" + N' FOR ' + QUOTENAME(N'{_escape_literal(res.column_name)}');\n"
            f"EXEC sys.sp_executesql @df_sql_{n};\n"
        )
    apply += f"PRINT N'Columna [{col_print}] de {table_lit} modificada con exito.';"
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
            "    DECLARE @bdiff_fk TABLE (fk_id int PRIMARY KEY, step int NOT NULL, recreate bit NOT NULL, name sysname NOT NULL,",
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
                    "SELECT create_sql FROM @bdiff_fk WHERE recreate = 1 ORDER BY fk_id",
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
    ts: datetime.datetime,
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
            lambda pos, t=t: _drop_table_step(t, pos, ts)
            for t in table_deletions
            if profile_name in t.profiles_to_update
        ]
        + [
            lambda pos, c=c: _drop_column_step(c, pos, ts)
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
        ts,
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
