import hashlib

from schema_comparator.domain.schema.models import (
    ColumnSnapshot,
    DefinitionAvailability,
    ParameterSnapshot,
    ProcedureSnapshot,
    SchemaFeature,
    SchemaSnapshot,
    TableSnapshot,
)


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
    c.ORDINAL_POSITION
FROM INFORMATION_SCHEMA.COLUMNS c
INNER JOIN INFORMATION_SCHEMA.TABLES t
    ON t.TABLE_SCHEMA = c.TABLE_SCHEMA
   AND t.TABLE_NAME = c.TABLE_NAME
WHERE t.TABLE_TYPE = 'BASE TABLE'
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
    normalized = "\n".join(line.rstrip() for line in sql.replace("\r\n", "\n").strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_snapshot(
    profile_name: str,
    rows: list[tuple],
    proc_rows: list[tuple] | None = None,
) -> SchemaSnapshot:
    """Group and sort raw catalog rows into a deterministic `SchemaSnapshot`."""
    grouped: dict[tuple[str, str], list[ColumnSnapshot]] = {}
    for (
        schema,
        table,
        col_name,
        data_type,
        char_len,
        num_prec,
        num_scale,
        is_nullable,
        ordinal,
    ) in rows:
        grouped.setdefault((schema, table), []).append(
            ColumnSnapshot(
                name=col_name,
                data_type=data_type,
                character_maximum_length=char_len,
                numeric_precision=num_prec,
                numeric_scale=num_scale,
                is_nullable=(is_nullable == "YES"),
                ordinal_position=ordinal,
            )
        )

    tables = tuple(
        TableSnapshot(
            schema_name=schema,
            table_name=table,
            columns=tuple(sorted(cols, key=lambda c: (c.ordinal_position, c.name))),
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
            params = tuple(sorted(data["params"], key=lambda p: (p.ordinal_position, p.name)))
            def_sql = data["def_sql"]
            is_enc = data["is_encrypted"]
            if is_enc or (def_sql is None and not is_enc):
                avail = DefinitionAvailability.ENCRYPTED if is_enc else DefinitionAvailability.NOT_VISIBLE
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
        extracted_features=frozenset({SchemaFeature.TABLES, SchemaFeature.ROUTINES}),
    )



# Alias for backward compatibility
_build_snapshot = build_snapshot
