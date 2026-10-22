import hashlib

from schema_comparator.domain.schema.models import (
    ColumnSnapshot,
    DefinitionAvailability,
    ForeignKeySnapshot,
    IndexSnapshot,
    ParameterSnapshot,
    PrimaryKeySnapshot,
    ProcedureSnapshot,
    SchemaFeature,
    SchemaSnapshot,
    TableSnapshot,
)


# Name given to a primary key SQL Server named itself, so two databases
# compare equal when only the generated suffix differs.
AUTO_PRIMARY_KEY_NAME = "PK (autogenerado)"

CATALOG_QUERY_SQL = """
SELECT
    c.TABLE_SCHEMA,
    c.TABLE_NAME,
    c.COLUMN_NAME,
    c.DATA_TYPE,
    c.CHARACTER_MAXIMUM_LENGTH,
    c.NUMERIC_PRECISION,
    c.NUMERIC_SCALE,
    c.IS_NULLABLE,
    c.ORDINAL_POSITION,
    c.COLUMN_DEFAULT,
    COLUMNPROPERTY(
        OBJECT_ID(QUOTENAME(c.TABLE_SCHEMA) + N'.' + QUOTENAME(c.TABLE_NAME)),
        c.COLUMN_NAME,
        'IsIdentity'
    ) AS IS_IDENTITY,
    -- Only a collation the column declares: one that follows the database
    -- default is not drift, or two databases with different defaults
    -- would differ in every text column.
    CASE WHEN c.COLLATION_NAME <> CONVERT(nvarchar(128), DATABASEPROPERTYEX(DB_NAME(), 'Collation'))
        THEN c.COLLATION_NAME END AS EXPLICIT_COLLATION,
    CASE WHEN c.DATA_TYPE IN ('datetime2', 'time', 'datetimeoffset')
        THEN c.DATETIME_PRECISION END AS DATETIME_PRECISION
FROM INFORMATION_SCHEMA.COLUMNS c
INNER JOIN INFORMATION_SCHEMA.TABLES t
    ON t.TABLE_SCHEMA = c.TABLE_SCHEMA
   AND t.TABLE_NAME = c.TABLE_NAME
WHERE t.TABLE_TYPE = 'BASE TABLE'
""".strip()

# Primary keys, foreign keys and indexes of the base tables. `is_system_named`
# marks the constraints SQL Server named itself (PK__Users__3213E83F...):
# that suffix differs from one database to the next, so `build_snapshot`
# replaces it with a name built from the structure.
PRIMARY_KEYS_QUERY_SQL = """
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    kc.name AS constraint_name,
    kc.is_system_named,
    c.name AS column_name,
    ic.key_ordinal
FROM sys.key_constraints kc
INNER JOIN sys.tables t ON t.object_id = kc.parent_object_id
INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
INNER JOIN sys.index_columns ic
    ON ic.object_id = kc.parent_object_id AND ic.index_id = kc.unique_index_id
INNER JOIN sys.columns c
    ON c.object_id = ic.object_id AND c.column_id = ic.column_id
WHERE kc.type = 'PK' AND t.is_ms_shipped = 0 AND ic.key_ordinal > 0
ORDER BY s.name, t.name, ic.key_ordinal
""".strip()

FOREIGN_KEYS_QUERY_SQL = """
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    fk.name AS constraint_name,
    fk.is_system_named,
    rs.name AS referenced_schema,
    rt.name AS referenced_table,
    pc.name AS column_name,
    rc.name AS referenced_column,
    fkc.constraint_column_id,
    fk.delete_referential_action_desc,
    fk.update_referential_action_desc
FROM sys.foreign_keys fk
INNER JOIN sys.tables t ON t.object_id = fk.parent_object_id
INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
INNER JOIN sys.tables rt ON rt.object_id = fk.referenced_object_id
INNER JOIN sys.schemas rs ON rs.schema_id = rt.schema_id
INNER JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
INNER JOIN sys.columns pc
    ON pc.object_id = fkc.parent_object_id AND pc.column_id = fkc.parent_column_id
INNER JOIN sys.columns rc
    ON rc.object_id = fkc.referenced_object_id
   AND rc.column_id = fkc.referenced_column_id
WHERE t.is_ms_shipped = 0
ORDER BY s.name, t.name, fk.name, fkc.constraint_column_id
""".strip()

# Rowstore indexes only (clustered and nonclustered); the primary key is the
# PK, not an index. A UNIQUE constraint shows up here under its own name.
INDEXES_QUERY_SQL = """
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    i.name AS index_name,
    i.is_unique,
    i.type AS index_type,
    i.filter_definition,
    ISNULL(kc.is_system_named, 0) AS is_system_named,
    c.name AS column_name,
    ic.key_ordinal,
    ic.is_descending_key,
    ic.is_included_column
FROM sys.indexes i
INNER JOIN sys.tables t ON t.object_id = i.object_id
INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
INNER JOIN sys.index_columns ic
    ON ic.object_id = i.object_id AND ic.index_id = i.index_id
INNER JOIN sys.columns c
    ON c.object_id = ic.object_id AND c.column_id = ic.column_id
LEFT JOIN sys.key_constraints kc
    ON kc.parent_object_id = i.object_id AND kc.unique_index_id = i.index_id
WHERE i.is_primary_key = 0
  AND i.is_hypothetical = 0
  AND i.type IN (1, 2)
  AND t.is_ms_shipped = 0
  AND (ic.key_ordinal > 0 OR ic.is_included_column = 1)
ORDER BY s.name, t.name, i.name, ic.is_included_column, ic.key_ordinal, ic.index_column_id
""".strip()

PROCEDURES_QUERY_SQL = """
SELECT
    s.name AS schema_name,
    o.name AS procedure_name,
    o.type_desc AS routine_type,
    m.definition AS definition_sql,
    OBJECTPROPERTY(o.object_id, 'IsEncrypted') AS is_encrypted,
    param.name AS parameter_name,
    TYPE_NAME(param.user_type_id) AS parameter_type,
    param.max_length AS max_length_bytes,
    param.precision,
    param.scale,
    param.is_output,
    param.parameter_id AS ordinal_position
FROM sys.objects o
INNER JOIN sys.schemas s ON o.schema_id = s.schema_id
LEFT JOIN sys.sql_modules m ON o.object_id = m.object_id
LEFT JOIN sys.parameters param ON o.object_id = param.object_id AND param.parameter_id >= 0
WHERE o.type IN ('P', 'FN', 'IF', 'TF') AND o.is_ms_shipped = 0
ORDER BY s.name, o.name, param.parameter_id
""".strip()


def _hash_definition(sql: str | None) -> str | None:
    if not sql:
        return None
    normalized = "\n".join(
        line.rstrip() for line in sql.replace("\r\n", "\n").strip().splitlines()
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _unique_name(name: str, taken: set[str]) -> str:
    """`name`, or `name #2`, `name #3`... when the table already has it."""
    candidate, n = name, 1
    while candidate in taken:
        n += 1
        candidate = f"{name} #{n}"
    taken.add(candidate)
    return candidate


def _column_list(columns: tuple[str, ...]) -> str:
    return ", ".join(columns)


def _primary_keys(rows: list[tuple]) -> dict[tuple[str, str], PrimaryKeySnapshot]:
    grouped: dict[tuple[str, str], tuple[str, bool, list[str]]] = {}
    for schema, table, name, is_system_named, column, _ordinal in rows:
        _, _, columns = grouped.setdefault(
            (schema, table), (name, bool(is_system_named), [])
        )
        columns.append(column)
    return {
        key: PrimaryKeySnapshot(
            name=AUTO_PRIMARY_KEY_NAME if is_system_named else name,
            columns=tuple(columns),
        )
        for key, (name, is_system_named, columns) in grouped.items()
    }


def _foreign_keys(
    rows: list[tuple],
) -> dict[tuple[str, str], tuple[ForeignKeySnapshot, ...]]:
    grouped: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        (schema, table, name, is_system_named, ref_schema, ref_table) = row[:6]
        column, ref_column, _ordinal, on_delete, on_update = row[6:11]
        fk = grouped.setdefault(
            (schema, table, name),
            {
                "system": bool(is_system_named),
                "ref_schema": ref_schema,
                "ref_table": ref_table,
                "columns": [],
                "ref_columns": [],
                "on_delete": on_delete,
                "on_update": on_update,
            },
        )
        fk["columns"].append(column)
        fk["ref_columns"].append(ref_column)

    by_table: dict[tuple[str, str], list[ForeignKeySnapshot]] = {}
    taken: dict[tuple[str, str], set[str]] = {}
    for (schema, table, name), fk in grouped.items():
        columns, ref_columns = tuple(fk["columns"]), tuple(fk["ref_columns"])
        if fk["system"]:
            name = (
                f"FK ({_column_list(columns)}) -> "
                f"{fk['ref_schema']}.{fk['ref_table']} ({_column_list(ref_columns)})"
            )
        by_table.setdefault((schema, table), []).append(
            ForeignKeySnapshot(
                name=_unique_name(name, taken.setdefault((schema, table), set())),
                columns=columns,
                referenced_table=fk["ref_table"],
                referenced_columns=ref_columns,
                referenced_schema=fk["ref_schema"],
                on_delete=_action(fk["on_delete"]),
                on_update=_action(fk["on_update"]),
            )
        )
    return {key: tuple(fks) for key, fks in by_table.items()}


def _action(description: str | None) -> str | None:
    """`NO_ACTION` -> `NO ACTION`, the way the DDL writes it."""
    return description.replace("_", " ") if description else None


def _indexes(rows: list[tuple]) -> dict[tuple[str, str], tuple[IndexSnapshot, ...]]:
    grouped: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        schema, table, name, is_unique, index_type, filter_sql, is_system_named = row[
            :7
        ]
        column, ordinal, is_descending, is_included = row[7:11]
        index = grouped.setdefault(
            (schema, table, name),
            {
                "unique": bool(is_unique),
                "clustered": index_type == 1,
                "filter": filter_sql,
                "system": bool(is_system_named),
                "keys": [],
                "descending": [],
                "included": [],
            },
        )
        if is_included:
            index["included"].append(column)
        else:
            index["keys"].append(column)
            if is_descending:
                index["descending"].append(column)

    by_table: dict[tuple[str, str], list[IndexSnapshot]] = {}
    taken: dict[tuple[str, str], set[str]] = {}
    for (schema, table, name), index in grouped.items():
        keys = tuple(index["keys"])
        if index["system"]:
            name = f"UQ ({_column_list(keys)})"
        by_table.setdefault((schema, table), []).append(
            IndexSnapshot(
                name=_unique_name(name, taken.setdefault((schema, table), set())),
                columns=keys,
                is_unique=index["unique"],
                is_clustered=index["clustered"],
                descending_columns=tuple(index["descending"]),
                included_columns=tuple(index["included"]),
                filter_expression=index["filter"],
            )
        )
    return {
        key: tuple(sorted(indexes, key=lambda i: i.name))
        for key, indexes in by_table.items()
    }


def build_snapshot(
    profile_name: str,
    rows: list[tuple],
    proc_rows: list[tuple] | None = None,
    primary_key_rows: list[tuple] | None = None,
    foreign_key_rows: list[tuple] | None = None,
    index_rows: list[tuple] | None = None,
) -> SchemaSnapshot:
    """Group and sort raw catalog rows into a deterministic `SchemaSnapshot`."""
    grouped: dict[tuple[str, str], list[ColumnSnapshot]] = {}
    for row in rows:
        (
            schema,
            table,
            col_name,
            data_type,
            char_len,
            num_prec,
            num_scale,
            is_nullable,
            ordinal,
        ) = row[:9]
        # Default, identity, explicit collation and time precision; rows
        # without them come from callers that predate those columns.
        default, identity, collation, dt_precision = (tuple(row[9:]) + (None,) * 4)[:4]
        grouped.setdefault((schema, table), []).append(
            ColumnSnapshot(
                name=col_name,
                data_type=data_type,
                character_maximum_length=char_len,
                numeric_precision=num_prec,
                numeric_scale=num_scale,
                is_nullable=(is_nullable == "YES"),
                ordinal_position=ordinal,
                default_expression=default,
                is_identity=bool(identity),
                collation=collation,
                datetime_precision=dt_precision,
            )
        )

    primary_keys = _primary_keys(primary_key_rows or [])
    foreign_keys = _foreign_keys(foreign_key_rows or [])
    indexes = _indexes(index_rows or [])
    tables = tuple(
        TableSnapshot(
            schema_name=schema,
            table_name=table,
            columns=tuple(sorted(cols, key=lambda c: (c.ordinal_position, c.name))),
            primary_key=primary_keys.get((schema, table)),
            foreign_keys=foreign_keys.get((schema, table), ()),
            indexes=indexes.get((schema, table), ()),
        )
        for (schema, table), cols in sorted(grouped.items())
    )

    procedures: list[ProcedureSnapshot] = []
    if proc_rows:
        proc_map: dict[tuple[str, str], dict] = {}
        for row in proc_rows:
            if not isinstance(row, (tuple, list)) or len(row) < 12:
                continue
            (
                schema,
                proc_name,
                routine_type,
                def_sql,
                is_encrypted,
                param_name,
                param_type,
                max_len_bytes,
                prec,
                scale,
                is_out,
                param_ord,
            ) = row[:12]
            key = (schema, proc_name)
            if key not in proc_map:
                proc_map[key] = {
                    "routine_type": routine_type or "PROCEDURE",
                    "def_sql": def_sql,
                    "is_encrypted": bool(is_encrypted),
                    "params": [],
                }
            if param_name is not None or param_ord == 0:
                p_type = param_type or "UNKNOWN"
                char_max_len = None
                if max_len_bytes is not None and max_len_bytes > 0:
                    if p_type.lower() in ("nvarchar", "nchar"):
                        char_max_len = max_len_bytes // 2
                    else:
                        char_max_len = max_len_bytes
                elif max_len_bytes == -1:
                    char_max_len = -1

                proc_map[key]["params"].append(
                    ParameterSnapshot(
                        name=param_name or "@RETURN_VALUE",
                        data_type=p_type,
                        max_length_bytes=max_len_bytes,
                        character_maximum_length=char_max_len,
                        numeric_precision=prec,
                        numeric_scale=scale,
                        is_output=bool(is_out),
                        is_return_value=(param_ord == 0),
                        ordinal_position=param_ord if param_ord is not None else 0,
                    )
                )

        for (schema, proc_name), data in sorted(proc_map.items()):
            params = tuple(
                sorted(data["params"], key=lambda p: (p.ordinal_position, p.name))
            )
            def_sql = data["def_sql"]
            is_enc = data["is_encrypted"]
            if is_enc or (def_sql is None and not is_enc):
                avail = (
                    DefinitionAvailability.ENCRYPTED
                    if is_enc
                    else DefinitionAvailability.NOT_VISIBLE
                )
                def_hash = None
            else:
                avail = DefinitionAvailability.AVAILABLE
                def_hash = _hash_definition(def_sql)

            procedures.append(
                ProcedureSnapshot(
                    schema_name=schema,
                    procedure_name=proc_name,
                    routine_type=data["routine_type"],
                    parameters=params,
                    definition_hash=def_hash,
                    definition_sql=def_sql,
                    definition_availability=avail,
                )
            )

    return SchemaSnapshot(
        profile_name=profile_name,
        provider_id="sqlserver",
        tables=tables,
        procedures=tuple(procedures),
        extracted_features=frozenset(
            {SchemaFeature.TABLES, SchemaFeature.ROUTINES, SchemaFeature.KEYS}
        ),
    )


# Alias for backward compatibility
_build_snapshot = build_snapshot
